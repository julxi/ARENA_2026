"""Rent a vast.ai GPU for the ARENA exercises, set it up, and bring the work back.

Julian works entirely on the rented machine (VS Code Remote-SSH). This script does everything around
that: `up` rents a machine, uploads the working tree (uncommitted changes and `.git` included), builds
the venv with vast/remote_setup.sh and opens VS Code on it; `pull` brings the work back; `down` pulls
and then destroys the machine. Only instances labelled `arena` are touched, so rentals from other
projects on the same vast.ai account are left alone. Design discussion and decisions:
convos/julian/26-10-27_vastai_gpu_setup_LOG.md. Adapted from the SPD project's run_vast.py, whose
rental code encodes lessons from failed rentals (taken offers, dead hosts, slow installs).

Run with the repo's venv (only the standard library and pyyaml are needed):
    .venv/bin/python vast/arena_vast.py offers       # browse matching offers, rent nothing
    .venv/bin/python vast/arena_vast.py up           # rent, upload, install, open VS Code
    .venv/bin/python vast/arena_vast.py status       # what is rented and what it has cost
    .venv/bin/python vast/arena_vast.py pull         # remote -> local, never deletes
    .venv/bin/python vast/arena_vast.py push         # local -> remote, never deletes
    .venv/bin/python vast/arena_vast.py down         # pull, then destroy
`--config rtx_3090` before the subcommand selects vast/rtx_3090.yaml (default: rtx_3060).
"""

import argparse
import dataclasses
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VAST_DIR = REPO_ROOT / "vast"
BLACKLIST_PATH = VAST_DIR / "blacklist.yaml"
DEFAULT_CONFIG = "rtx_3060"
# The vast.ai label that marks our instances; everything else on the account is someone else's.
LABEL = "arena"
SSH_ALIAS = "arena"
SSH_CONFIG_PATH = Path.home() / ".ssh/config.d/arena.conf"
# The key Julian's account already has on vast.ai (the SPD project rents with it).
IDENTITY_FILE = Path.home() / ".ssh/id_rsa"
REMOTE_REPO_DIR = f"/root/{REPO_ROOT.name}"
REMOTE_SETUP_SCRIPT = f"{REMOTE_REPO_DIR}/vast/remote_setup.sh"
READY_TIMEOUT_S = 900
POLL_INTERVAL_S = 10
SSH_READY_TIMEOUT_S = 300
SSH_POLL_INTERVAL_S = 5
# GNU coreutils `timeout` reports this when it kills the command it wrapped.
TIMEOUT_EXIT = 124
# vast.ai reports these when the host has dropped off its control plane. It keeps claiming
# intended_status "running", but the container never finishes provisioning.
DEAD_STATUSES = frozenset({"missing", "exited"})
# vast.ai's error for an ask it will not rent out: rented by someone else, or unavailable although
# the search listed it (e.g. its host went offline).
TAKEN_OFFER_ERROR = "no_such_ask"
# How many changed files a sync preview lists by name before summarizing the rest.
PREVIEW_LIMIT = 40


def log(message: str) -> None:
    print(f"[arena-vast] {message}", flush=True)


class HostFailure(Exception):
    """A rental that failed because of the host, not because of us, so the host is blacklisted.

    `reason` is the short form that goes into the blacklist; the exception message is the full
    explanation shown to the user. `cmd_up` blacklists the host and destroys the instance.
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class VastConfig:
    """Machine selection, loaded from vast/<name>.yaml (one file per GPU type)."""

    gpu_name: str  # vast.ai GPU name, spaces as underscores (e.g. 'RTX_3060')
    min_gpu_ram: int  # GB; vast.ai filters gpu_ram in GB but reports it in MB
    max_price: float  # $/hour including storage; pricier offers are not searched
    warn_price: float  # $/hour; renting above this asks for confirmation
    disk: int  # GB to rent; also filters out machines with less free disk
    image: str  # docker image; must ship uv and git (see remote_setup.sh)
    min_cuda: float  # minimum CUDA the host driver supports, matched to the torch wheels
    min_reliability: float
    # True rents only hosts vast.ai lists as datacenters. False searches all hosts; it does not
    # exclude datacenters.
    datacenter_only: bool
    excluded_countries: list[str]  # two-letter codes, e.g. ['CN']
    min_inet_down: float  # Mbps, self-reported by the host
    sort: str  # vast.ai sort order; the first offer is rented
    n_offers: int
    # Budget for remote_setup.sh. A host with a slow route to PyPI stalls here for tens of
    # minutes, which its advertised inet_down does not predict.
    max_install_minutes: float

    @classmethod
    def load(cls, name: str) -> "VastConfig":
        path = VAST_DIR / f"{name}.yaml"
        available = sorted(p.stem for p in VAST_DIR.glob("*.yaml") if p != BLACKLIST_PATH)
        assert path.exists(), f"vast config not found: {path}. Available: {', '.join(available)}"
        data = yaml.safe_load(path.read_text())
        expected = {f.name for f in dataclasses.fields(cls)}
        assert set(data) == expected, (
            f"{path.name}: missing fields {sorted(expected - set(data))}, "
            f"unknown fields {sorted(set(data) - expected)}"
        )
        config = cls(**data)
        assert config.warn_price < config.max_price, (
            f"{path.name}: warn_price {config.warn_price} must be below max_price {config.max_price}"
        )
        log(f"Machine config: vast/{path.name}")
        return config


# --- vast.ai CLI -----------------------------------------------------------------------------------


def _vastai(args: list[str], raw: bool = True) -> Any:
    """Run a vastai CLI command, parsing its JSON output when raw.

    Under `--raw` the CLI reports an API failure by printing a JSON error object to stderr and
    exiting 0 with an empty stdout, so empty stdout means the command failed. Only the leading
    tokens of a failed command are reported, to keep arguments such as ssh keys out of the error.

    stdin is closed so that a command which prompts for confirmation aborts at once instead of
    waiting on an invisible prompt; the CLI still exits 0 then, so such commands check their output.

    Deprecated commands (e.g. `show instances`, replaced by `show instances-v1`) print a notice
    before their JSON, which makes it unparsable; vastai 1.2.0, checked 26-10-27.
    """
    cmd = ["vastai", *args, "--raw"] if raw else ["vastai", *args]
    result = subprocess.run(
        cmd, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    if not raw:
        return result.stdout
    stdout = result.stdout.strip()
    redacted_command = shlex.join(["vastai", *args[:3]])
    assert stdout, f"`{redacted_command}` failed: {result.stderr.strip() or 'no error message'}"
    return json.loads(stdout)


def _list_instances() -> list[dict[str, Any]]:
    """All instances on the account, ours and other projects'.

    The raw instance dicts carry the container's env vars (e.g. another project's WandB key in
    `extra_env`), so they are never printed whole.
    """
    shown = _vastai(["show", "instances-v1", "--all"])
    assert shown["success"], f"`vastai show instances-v1` did not succeed: keys {sorted(shown)}"
    assert shown["next_token"] is None, "`--all` should have fetched every page"
    return shown["instances"]


def _our_instance() -> dict[str, Any]:
    """The one `arena` instance that push/pull/down act on."""
    ours = [i for i in _list_instances() if i["label"] == LABEL]
    assert ours, f"No instance labelled '{LABEL}' is rented. Rent one with `up`."
    assert len(ours) == 1, (
        f"{len(ours)} instances are labelled '{LABEL}' ({[i['id'] for i in ours]}), expected one. "
        f"Destroy the extra ones with `vastai destroy instance <id> -y`."
    )
    return ours[0]


def _show_instance(instance_id: int) -> dict[str, Any]:
    """Look an instance up, failing loudly if it has vanished.

    An instance whose host drops it stops existing rather than reporting a dead status, and
    `show instance` answers for it with `{"instances": null}` instead of the flat instance dict.
    """
    shown = _vastai(["show", "instance", str(instance_id)])
    if "actual_status" not in shown:
        raise HostFailure(
            "host dropped the rental",
            f"Instance {instance_id} no longer exists (response keys {sorted(shown)}). Its host "
            f"dropped it, which vast.ai reports by forgetting the rental rather than marking it "
            f"dead. Run `up` again to land on a different host.",
        )
    return shown


def _destroy_instance(instance_id: int) -> None:
    """Destroy an instance, failing loudly unless vast.ai confirms it.

    The CLI exits 0 whatever happens: on success it prints "destroying instance <id>.", on an
    unknown instance "Failed with error 404: ..." (to stderr), and without `-y` it prompts, reads
    a closed stdin and prints "Aborted." [observed with vastai 1.2.0 in the SPD project, 26-10-06].
    So the output is the only signal. A 404 is accepted because a dropped instance is already gone.
    """
    log(f"Destroying instance {instance_id}")
    result = subprocess.run(
        ["vastai", "destroy", "instance", str(instance_id), "-y"],
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    output = (result.stdout + result.stderr).strip()
    log(output)
    assert output == f"destroying instance {instance_id}." or "error 404" in output, (
        f"vast.ai did not confirm destroying instance {instance_id} ({output!r}), so it may still "
        f"be billing. Check `vastai show instances-v1` and destroy it with: "
        f"vastai destroy instance {instance_id} -y"
    )


# --- Offers and renting ----------------------------------------------------------------------------


def _load_blacklist() -> list[dict[str, Any]]:
    hosts = yaml.safe_load(BLACKLIST_PATH.read_text())["hosts"]
    host_ids = [h["host_id"] for h in hosts]
    assert len(host_ids) == len(set(host_ids)), f"Duplicate host ids in {BLACKLIST_PATH}"
    return hosts


def _add_to_blacklist(host_id: int, reason: str) -> None:
    """Append a host to the git-tracked blacklist, keeping the file's comment header."""
    hosts = _load_blacklist()
    assert host_id not in {h["host_id"] for h in hosts}, (
        f"Host {host_id} failed but is already blacklisted - the search should have excluded it"
    )
    text = BLACKLIST_PATH.read_text()
    header = text[: text.index("\nhosts:") + 1]
    entry = {"host_id": host_id, "date": datetime.now().strftime("%y-%m-%d"), "reason": reason}
    body = yaml.safe_dump({"hosts": [*hosts, entry]}, sort_keys=False, width=100)
    BLACKLIST_PATH.write_text(header + body)
    log(f"Blacklisted host {host_id} in vast/{BLACKLIST_PATH.name}: {reason}")


def _search_offers(config: VastConfig, blacklisted: list[int]) -> list[dict[str, Any]]:
    """Search offers in the config's sort order; the caller rents the first available one.

    `disk_space` is the machine's free disk, which must fit the disk we rent. `direct_port_count>=1`
    is required for `--direct` ssh, which vast.ai's docs call faster and more reliable than its
    proxy. The datacenter term is added only when required, because `datacenter=false` would
    restrict the search to non-datacenter hosts. `host_id` is missing from the CLI's documented
    query fields (it worked in the SPD project), so the result is checked for leaks too.
    """
    query = (
        f"num_gpus=1 gpu_name={config.gpu_name} rentable=true verified=true "
        f"reliability>{config.min_reliability} direct_port_count>=1 "
        f"cuda_max_good>={config.min_cuda} gpu_ram>={config.min_gpu_ram} "
        f"disk_space>={config.disk} inet_down>={config.min_inet_down} "
        f"dph_total<{config.max_price}"
    )
    if config.datacenter_only:
        query += " datacenter=true"
    if config.excluded_countries:
        query += f" geolocation notin [{','.join(config.excluded_countries)}]"
    if blacklisted:
        query += f" host_id notin [{','.join(map(str, blacklisted))}]"
    log(f"Searching offers: {query}")
    offers = _vastai(
        [
            "search",
            "offers",
            query,
            "-o",
            config.sort,
            "--limit",
            str(config.n_offers),
            # Price storage for the disk we actually rent; vast.ai otherwise quotes it for 5 GB.
            "--storage",
            str(config.disk),
        ]
    )
    assert offers, (
        f"No offers matched. Raise max_price or relax the filters in vast/<config>.yaml. "
        f"{len(blacklisted)} hosts are excluded by vast/{BLACKLIST_PATH.name}."
    )
    leaked = sorted({o["host_id"] for o in offers} & set(blacklisted))
    assert not leaked, f"vast.ai ignored the host_id exclusion and returned blacklisted {leaked}"
    for offer in offers:
        _assert_allowed_country(offer, config.excluded_countries)
    return offers


def _assert_allowed_country(offer: dict[str, Any], excluded: list[str]) -> None:
    """vast.ai reports `geolocation` as 'Region, CC' (e.g. 'Jiangsu, CN'; checked 26-10-26)."""
    geo = offer["geolocation"]
    assert isinstance(geo, str) and ", " in geo, (
        f"Offer {offer['id']} has geolocation {geo!r}, expected 'Region, CC'; its country cannot "
        f"be checked against excluded_countries {excluded}"
    )
    country = geo.rsplit(", ", 1)[1]
    assert country not in excluded, f"Offer {offer['id']} is in {geo}, an excluded country"


def _print_offers(offers: list[dict[str, Any]], config: VastConfig) -> None:
    """'host' is the operator id the blacklist excludes; 'free' is the machine's unallocated disk."""
    log(
        f"{len(offers)} matching offers, sorted by {config.sort}. $/hr includes the "
        f"{config.disk} GB disk; offers above ${config.warn_price}/hr ask before renting"
    )
    print(
        f"{'id':>10} {'host':>7}  {'gpu':<10} {'vram':>5} {'$/hr':>6} {'free':>6} {'cuda':>5} "
        f"{'net↓':>7} {'dlperf/$':>8} {'reliab':>7}  location"
    )
    for o in offers:
        print(
            f"{o['id']:>10} {o['host_id']:>7}  {o['gpu_name']:<10} {o['gpu_ram'] / 1024:>4.0f}G "
            f"{o['dph_total']:>6.3f} {o['disk_space']:>5.0f}G {o['cuda_max_good']:>5.1f} "
            f"{o['inet_down']:>6.0f}M {o['dlperf_per_dphtotal']:>8.1f} "
            f"{o['reliability']:>7.4f}  {o['geolocation']}"
        )


def _confirm(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() == "y"


def _create_instance(offer_id: int, config: VastConfig) -> int | None:
    """Rent an offer, returning None if it is not available. Nothing is rented on failure.

    `--cancel-unavail` makes vast.ai reject an unavailable ask outright instead of parking a
    stopped instance on us, and it reports that as `no_such_ask`. This does not go through
    `_vastai` because an unavailable ask is an expected outcome here, not an error.
    """
    args = [
        "vastai", "create", "instance", str(offer_id),
        "--image", config.image,
        "--disk", str(config.disk),
        "--ssh", "--direct",
        "--label", LABEL,
        "--cancel-unavail",
        "--raw",
    ]  # fmt: skip
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    stdout = result.stdout.strip()
    if not stdout:
        stderr = result.stderr.strip()
        assert TAKEN_OFFER_ERROR in stderr, f"`vastai create instance` failed: {stderr or '-'}"
        return None
    created = json.loads(stdout)
    assert created["success"], f"Failed to create instance: {created}"
    return int(created["new_contract"])


def _rent_first_available(
    offers: list[dict[str, Any]], config: VastConfig
) -> tuple[int, dict[str, Any]]:
    """Rent the best offer still on the market, walking down the search order.

    vast.ai's search serves asks that are already gone, so the top offer is regularly unavailable
    by the time we ask for it; only that moves us on to the next offer.
    """
    for offer in offers:
        offer_id = int(offer["id"])
        price = offer["dph_total"]
        if price > config.warn_price and not _confirm(
            f"Offer {offer_id} costs ${price:.3f}/hr, above warn_price ${config.warn_price}/hr. "
            f"Rent it?"
        ):
            sys.exit("Nothing rented.")
        log(
            f"Renting offer {offer_id}: {offer['gpu_name']} at ${price:.3f}/hr in "
            f"{offer['geolocation']} (reliability {offer['reliability']:.4f}, host {offer['host_id']})"
        )
        instance_id = _create_instance(offer_id, config)
        if instance_id is not None:
            return instance_id, offer
        log(f"Offer {offer_id} is no longer available - trying the next one")
    raise AssertionError(
        f"None of the {len(offers)} matching offers was available. Run `up` again - the search "
        f"index lags the marketplace by minutes, so a fresh search lists different asks."
    )


def _wait_until_running(instance_id: int) -> None:
    deadline = time.time() + READY_TIMEOUT_S
    while time.time() < deadline:
        instance = _show_instance(instance_id)
        status = instance["actual_status"]
        message = (instance["status_msg"] or "no message").strip()
        if status == "running":
            return
        if status in DEAD_STATUSES:
            raise HostFailure(
                f"instance went '{status}' while booting",
                f"Instance {instance_id} is '{status}' ({message}). "
                f"The host has dropped off vast.ai's control plane.",
            )
        # The container exists but Docker on the host refused to start it, and vast.ai does not
        # retry: e.g. "OCI runtime create failed ... unresolvable CDI devices ..." (the host's GPU
        # could not be attached; instance 58009521, 26-10-27). Waiting out READY_TIMEOUT_S only
        # bills for a machine that will never boot.
        if status == "created" and "Error response from daemon" in message:
            raise HostFailure(
                f"container failed to start: {message[:120]}",
                f"Instance {instance_id}: Docker on the host could not start the container:\n"
                f"{message}",
            )
        log(f"Instance status: {status} ({message})")
        time.sleep(POLL_INTERVAL_S)
    raise HostFailure(
        f"not running after {READY_TIMEOUT_S}s",
        f"Instance {instance_id} not running after {READY_TIMEOUT_S}s.",
    )


# --- ssh -------------------------------------------------------------------------------------------


def _attach_ssh_key(instance_id: int) -> None:
    """Push our public key to the instance through vast.ai's control plane.

    vast.ai's entrypoint copies account-level keys into authorized_keys at container start, but on
    some hosts that is slow or never happens, and there is no other way in to fix it. Attaching is
    idempotent, so it runs on every rental.
    """
    public_key = IDENTITY_FILE.with_name(IDENTITY_FILE.name + ".pub")
    assert public_key.exists(), f"public key not found: {public_key}"
    _vastai(["attach", "ssh", str(instance_id), public_key.read_text().strip()], raw=False)


def _write_ssh_config(instance_id: int) -> None:
    """Point the `arena` ssh alias at the instance, from `vastai ssh-url`.

    Rewritten by every subcommand rather than only by `up`, so the alias stays right if the
    instance's address changes (e.g. after a stop and restart). Host keys are not checked because
    every rental is a fresh machine, often reusing an ip:port that a previous rental had.
    """
    ssh_url = _vastai(["ssh-url", str(instance_id)], raw=False).strip()
    assert ssh_url.startswith("ssh://"), f"Unexpected ssh url: {ssh_url}"
    host, port = ssh_url.removeprefix("ssh://").split("@")[-1].split(":")
    SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SSH_CONFIG_PATH.write_text(
        f"# generated by vast/arena_vast.py (ARENA repo) for instance {instance_id} "
        f"at {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"Host {SSH_ALIAS}\n"
        f"    HostName {host}\n"
        f"    User root\n"
        f"    IdentityFile {IDENTITY_FILE}\n"
        f"    Port {int(port)}\n"
        f"    StrictHostKeyChecking no\n"
        f"    UserKnownHostsFile /dev/null\n"
    )


def _wait_until_ssh_ready(instance_id: int) -> None:
    """Poll until sshd accepts our key, re-attaching it once halfway through.

    `actual_status == "running"` only means the container started: the entrypoint installs
    authorized_keys a few seconds later. A host that rejects the key often accepts it minutes
    later, so the loop keeps polling through "Permission denied".
    """
    log("Waiting for ssh to accept our key")
    deadline = time.time() + SSH_READY_TIMEOUT_S
    reattach_at = time.time() + SSH_READY_TIMEOUT_S / 2
    reattached = False
    last_error = "<no probe ran>"
    while time.time() < deadline:
        probe = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", SSH_ALIAS, "true"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return
        last_error = probe.stderr.strip() or f"exit code {probe.returncode}, no stderr"
        if not reattached and time.time() >= reattach_at:
            log(f"ssh still failing ({last_error}) - re-attaching the key")
            _attach_ssh_key(instance_id)
            reattached = True
        time.sleep(SSH_POLL_INTERVAL_S)
    status = _show_instance(instance_id)["actual_status"]
    # Blacklisted although a broken local key would fail the same way: the key works for SPD's
    # rentals, so the host is the far likelier culprit.
    raise HostFailure(
        f"ssh failing after {SSH_READY_TIMEOUT_S}s: {last_error.splitlines()[-1]}",
        f"ssh to {SSH_ALIAS} still failing after {SSH_READY_TIMEOUT_S}s while instance "
        f"{instance_id} reports '{status}'.\nLast ssh error: {last_error}\n"
        f"Read the entrypoint's own account with: vastai logs {instance_id}",
    )


def _ssh(remote_command: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["ssh", SSH_ALIAS, remote_command], check=True, capture_output=capture, text=True
    )
    return result.stdout if capture else ""


# --- Syncing the working tree ----------------------------------------------------------------------


def _tree_files(remote: bool) -> list[str]:
    """The files git considers part of the working tree, on the sync's source side, plus `.git`.

    That is tracked files plus untracked files that are not gitignored, i.e. exactly what
    `git status` covers. git decides rather than an rsync filter because rsync reads .gitignore
    differently: a negation such as ARENA's `!chapter1_.../part32_.../data` would not re-include
    the tracked data folder. Tracked files deleted from the working tree are dropped, or rsync
    would fail on them. `.git` goes along so commits can be made on either side.
    """

    def git_ls(*flags: str) -> set[str]:
        command = ["git", "ls-files", "-z", *flags]
        if remote:
            out = _ssh(f"cd {REMOTE_REPO_DIR} && {shlex.join(command)}", capture=True)
        else:
            out = subprocess.run(
                command, cwd=REPO_ROOT, check=True, capture_output=True, text=True
            ).stdout
        return {p for p in out.split("\0") if p}

    files = git_ls("--cached", "--others", "--exclude-standard") - git_ls("--deleted")
    assert files, "git listed no files - is this the repo root?"
    return [".git", *sorted(files)]


def _rsync_args(push: bool, dry_run: bool) -> list[str]:
    """rsync of `_tree_files`, from local to remote (push) or back (pull).

    Never `--delete`: the work happens on the remote, and a push with deletions would wipe files
    created there since the last sync. `-rlptz` keeps permissions and mtimes but not ownership,
    because the remote runs as root and git refuses a repo owned by another uid. `-r` only matters
    for `.git`, the one directory in the file list.
    """
    local, remote = f"{REPO_ROOT}/", f"{SSH_ALIAS}:{REMOTE_REPO_DIR}/"
    src, dst = (local, remote) if push else (remote, local)
    progress = ["--dry-run", "--itemize-changes"] if dry_run else ["--info=progress2"]
    return ["rsync", "-rlptz", "--from0", "--files-from=-", *progress, src, dst]


def _rsync(push: bool, files: list[str], dry_run: bool = False) -> str:
    result = subprocess.run(
        _rsync_args(push, dry_run),
        input="\0".join(files),
        check=True,
        text=True,
        capture_output=dry_run,
    )
    return result.stdout if dry_run else ""


def _preview(push: bool, files: list[str]) -> list[str]:
    """Show what a sync would change; return the existing files it would overwrite (outside .git).

    rsync's itemized lines are an 11-character change code and a path, e.g. `<f+++++++++ a.py` (new
    file sent), `>f.st...... b.py` (existing file received with new content). `.git` internals
    always change and are only counted.
    """
    target = "remote" if push else "local"
    new, updated, git_internal = [], [], 0
    for line in _rsync(push, files, dry_run=True).splitlines():
        code, path = line.split(" ", 1)
        assert len(code) == 11, f"Unexpected rsync itemize line: {line!r}"
        if code[1] not in "fL" or code[0] not in "<>":
            continue  # directories, attribute-only changes
        if path == ".git" or path.startswith(".git/"):
            git_internal += 1
        elif code[2:] == "+" * 9:
            new.append(path)
        else:
            updated.append(path)
    log(
        f"Sync preview: {len(new)} new and {len(updated)} overwritten {target} files, plus "
        f"{git_internal} files inside .git"
    )
    for label, paths in (("new", new), ("OVERWRITE", updated)):
        for path in paths[:PREVIEW_LIMIT]:
            print(f"  {label:>9}  {path}")
        if len(paths) > PREVIEW_LIMIT:
            print(f"  {label:>9}  ... and {len(paths) - PREVIEW_LIMIT} more")
    return updated


def _copy_env_file() -> None:
    """Copy `.env` (API keys; gitignored, so never part of the tree sync) with owner-only access."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        log("No .env here, so none copied. Later chapters need keys (WandB, Hugging Face, OpenAI)")
        return
    subprocess.run(
        ["rsync", "--chmod=F600", str(env_file), f"{SSH_ALIAS}:{REMOTE_REPO_DIR}/.env"], check=True
    )
    log("Copied .env (mode 600)")


# --- Remote setup ----------------------------------------------------------------------------------


def _run_remote_setup(max_install_minutes: float) -> None:
    """Run remote_setup.sh, rejecting the host if it takes too long.

    `timeout` runs remotely, so a host that blows the budget is left with nothing still running.
    """
    budget_s = int(max_install_minutes * 60)
    log(f"Installing the venv (budget {max_install_minutes} min)")
    start = time.time()
    returncode = subprocess.run(
        ["ssh", SSH_ALIAS, f"timeout {budget_s} bash -l {REMOTE_SETUP_SCRIPT}"], check=False
    ).returncode
    if returncode == TIMEOUT_EXIT:
        raise HostFailure(
            f"install over {max_install_minutes} min",
            f"remote_setup.sh was still running after {max_install_minutes} min. This host's "
            f"route to PyPI is too slow.",
        )
    assert returncode == 0, f"remote_setup.sh failed on the rented machine with exit {returncode}"
    log(f"Venv installed in {(time.time() - start) / 60:.1f} min")


def _check_gpu() -> None:
    """torch must see the GPU; if not, the host's driver is older than its advertised CUDA."""
    check = (
        "import torch; assert torch.cuda.is_available(); "
        "print(torch.__version__, torch.cuda.get_device_name())"
    )
    probe = subprocess.run(
        ["ssh", SSH_ALIAS, f"{REMOTE_REPO_DIR}/.venv/bin/python -c {shlex.quote(check)}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise HostFailure(
            "torch.cuda.is_available() is False",
            f"torch cannot use the GPU on this host:\n{probe.stderr.strip()}",
        )
    log(f"GPU check passed: {probe.stdout.strip()}")


def _configure_remote_git() -> None:
    """Copy the local git identity, so commits made on the machine are attributed like local ones."""
    for key in ("user.name", "user.email"):
        value = subprocess.run(
            ["git", "config", key], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        _ssh(f"git config --global {key} {shlex.quote(value)}")


# --- Subcommands -----------------------------------------------------------------------------------


def cmd_offers(config: VastConfig, _args: argparse.Namespace) -> None:
    blacklisted = [h["host_id"] for h in _load_blacklist()]
    _print_offers(_search_offers(config, blacklisted), config)


def cmd_up(config: VastConfig, args: argparse.Namespace) -> None:
    existing = [i["id"] for i in _list_instances() if i["label"] == LABEL]
    assert not existing, (
        f"An '{LABEL}' instance is already rented ({existing}). Use `status`, or `down` first."
    )
    assert IDENTITY_FILE.exists(), f"ssh key not found: {IDENTITY_FILE}"
    blacklisted = [h["host_id"] for h in _load_blacklist()]
    offers = _search_offers(config, blacklisted)
    _print_offers(offers, config)

    start = time.time()
    instance_id, offer = _rent_first_available(offers, config)
    log(f"Created instance {instance_id} on host {offer['host_id']}, waiting for it to boot")
    try:
        _wait_until_running(instance_id)
        _attach_ssh_key(instance_id)
        _write_ssh_config(instance_id)
        _wait_until_ssh_ready(instance_id)
        _ssh(f"mkdir -p {REMOTE_REPO_DIR}")
        log("Uploading the working tree")
        _rsync(push=True, files=_tree_files(remote=False))
        _copy_env_file()
        _configure_remote_git()
        _run_remote_setup(config.max_install_minutes)
        _check_gpu()
    except HostFailure as failure:
        # Intentionally no automatic retry on the next offer: Julian decides on a relaunch himself
        # (same choice as in the SPD project).
        _add_to_blacklist(
            int(offer["host_id"]),
            f"{failure.reason} (instance {instance_id}, {offer['gpu_name']}, {offer['geolocation']})",
        )
        _destroy_instance(instance_id)
        raise
    except BaseException:
        log(
            f"Instance {instance_id} is still rented and billing. Retry by hand, or destroy it "
            f"with `down` (`down --no-pull` if it never booted)"
        )
        raise

    log(
        f"Ready after {(time.time() - start) / 60:.1f} min: instance {instance_id}, "
        f"{offer['gpu_name']} at ${offer['dph_total']:.3f}/hr in {offer['geolocation']}"
    )
    log(
        f"Connect: `ssh {SSH_ALIAS}`, or VS Code Remote-SSH host '{SSH_ALIAS}' -> {REMOTE_REPO_DIR}"
    )
    log("It bills until destroyed. End the session with: .venv/bin/python vast/arena_vast.py down")
    if args.no_code:
        return
    subprocess.run(["code", "--remote", f"ssh-remote+{SSH_ALIAS}", REMOTE_REPO_DIR], check=True)


def cmd_status(_config: VastConfig | None, _args: argparse.Namespace) -> None:
    instances = _list_instances()
    if not instances:
        log("No instances rented on this vast.ai account.")
        return
    now = time.time()
    for i in instances:
        hours = (now - i["start_date"]) / 3600
        owner = "" if i["label"] == LABEL else "   <- not ours, another project's"
        print(
            f"{i['id']:>10}  label={i['label']}  {i['actual_status']:<8} {i['gpu_name']:<10} "
            f"${i['dph_total']:.3f}/hr  up {hours:.1f} h  ~${i['dph_total'] * hours:.2f} so far  "
            f"host {i['host_id']}, {i['geolocation']}{owner}"
        )


def cmd_push(_config: VastConfig | None, _args: argparse.Namespace) -> None:
    _write_ssh_config(_our_instance()["id"])
    files = _tree_files(remote=False)
    if _preview(push=True, files=files) and not _confirm(
        "Overwrite these files on the remote machine (work done there since the last sync is lost)?"
    ):
        sys.exit("Nothing pushed.")
    _rsync(push=True, files=files)
    _copy_env_file()
    log(
        "Pushed. Changed requirements.txt? Re-run the install: ssh arena bash -l "
        + REMOTE_SETUP_SCRIPT
    )


def _pull(files: list[str], question: str) -> None:
    if not _confirm(f"{question} (OVERWRITE = local files replaced by the remote version)"):
        sys.exit("Nothing pulled.")
    _rsync(push=False, files=files)
    log("Pulled. Review and commit locally as usual (`git status`).")


def cmd_pull(_config: VastConfig | None, _args: argparse.Namespace) -> None:
    _write_ssh_config(_our_instance()["id"])
    files = _tree_files(remote=True)
    if _preview(push=False, files=files):
        _pull(files, "Pull these changes?")
        return
    _rsync(push=False, files=files)
    log("Pulled (no local file was overwritten).")


def cmd_down(_config: VastConfig | None, args: argparse.Namespace) -> None:
    """Pull, then destroy. Destroys nothing if the pull fails: the machine's work would be lost.

    `--no-pull` is the way out for a machine that cannot be pulled from, e.g. one whose container
    never started (instance 58009521, 26-10-27: `down` died on ssh with nothing to pull).
    """
    instance = _our_instance()
    instance_id = instance["id"]
    status = instance["actual_status"]
    if args.no_pull:
        # Intentionally no confirmation: typing the flag is the confirmation (Julian, 26-10-27).
        log(f"Destroying instance {instance_id} (status '{status}') without pulling")
    else:
        assert status == "running", (
            f"Instance {instance_id} is '{status}' ({instance['status_msg'] or 'no message'}), so "
            f"there is nothing to pull from. Nothing destroyed. If it never booted: `down "
            f"--no-pull`. If it was stopped: `vastai start instance {instance_id}`, then `down`."
        )
        _write_ssh_config(instance_id)
        try:
            files = _tree_files(remote=True)
            _preview(push=False, files=files)
            _pull(files, f"Pull these changes and then DESTROY instance {instance_id}?")
        except subprocess.CalledProcessError as error:
            raise AssertionError(
                f"Pulling from instance {instance_id} failed ({error}). Nothing destroyed. Retry, "
                f"or if the machine is unreachable for good: `down --no-pull`."
            ) from error
    _destroy_instance(instance_id)
    # A stale alias would point at an ip:port that vast.ai hands to the next renter. missing_ok
    # because with --no-pull this run may not have written it (e.g. after a failed `up`).
    SSH_CONFIG_PATH.unlink(missing_ok=True)
    log(f"Removed {SSH_CONFIG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="machine config name: vast/<name>.yaml"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("offers", help="list matching offers, rent nothing")
    up = sub.add_parser("up", help="rent, upload, install, open VS Code")
    up.add_argument("--no-code", action="store_true", help="don't open VS Code at the end")
    sub.add_parser("status", help="list instances on the account and their cost so far")
    sub.add_parser("push", help="upload local changes (asks before overwriting remote files)")
    sub.add_parser("pull", help="bring remote work back (never deletes local files)")
    down = sub.add_parser("down", help="pull, then destroy the instance")
    down.add_argument(
        "--no-pull",
        action="store_true",
        help="destroy without pulling, for a machine that never booted or is unreachable",
    )
    args = parser.parse_args()

    handlers = {
        "offers": cmd_offers,
        "up": cmd_up,
        "status": cmd_status,
        "push": cmd_push,
        "pull": cmd_pull,
        "down": cmd_down,
    }
    # Only renting needs the machine config; the other commands act on the rented instance.
    config = VastConfig.load(args.config) if args.command in ("offers", "up") else None
    handlers[args.command](config, args)


if __name__ == "__main__":
    main()
