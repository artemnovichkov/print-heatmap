"""print-heatmap: GitHub-style heatmap of your Bambu Lab 3D printing.

  print-heatmap login --repo you/you         get BAMBU_TOKEN, store it as a repo secret
  print-heatmap update --svg heatmap.svg     fetch history, update prints.json, render
  print-heatmap update --demo --svg demo.svg try it without an account
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta

from . import archive, cloud, demo, gist, stats, svg, text


def ask(prompt):
    # Prompts go to stderr, so stdout carries only the token: `print-heatmap login | pbcopy`.
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line:
        sys.exit("\naborted")
    return line.strip()


def log(msg):
    print(msg, file=sys.stderr)


def timezone_arg(name):
    if not name:
        return datetime.now().astimezone().tzinfo
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    return ZoneInfo(name)


def cmd_login(args):
    email = args.email or ask("Bambu Lab account email: ")
    cloud.send_code(email, args.region)
    log(f"A sign-in code was sent to {email}.")
    for attempt in range(3):
        code = ask("Code from the email: ")
        try:
            result = cloud.login_with_code(email, code, args.region)
            break
        except cloud.AuthError as e:
            if "wrong code" not in str(e) or attempt == 2:
                raise
            log("Wrong code, try again.")
    if "tfa_key" in result:
        result = cloud.login_tfa(result["tfa_key"], ask("Two-factor code: "), args.region)

    token = result["token"]
    if result.get("expires_in"):
        expires = date.today() + timedelta(seconds=int(result["expires_in"]))
        log(f"The token is valid until about {expires}: sign in again then.")

    if args.repo:
        if not shutil.which("gh"):
            sys.exit("--repo needs the GitHub CLI (https://cli.github.com); or drop --repo to print the token")
        subprocess.run(["gh", "secret", "set", args.secret, "--repo", args.repo], input=token, text=True, check=True)
        log(f"Saved as the {args.secret} secret of {args.repo}.")
    else:
        print(token)


def cmd_update(args):
    tz = timezone_arg(args.timezone)
    end = args.end or datetime.now(tz).date()

    if args.demo:
        records = demo.records(end)
    else:
        records = archive.load(args.archive)
        if not args.offline:
            token = os.environ.get("BAMBU_TOKEN")
            if not token:
                sys.exit("Set BAMBU_TOKEN (see `print-heatmap login`), or pass --offline or --demo")
            fresh = [r for r in (archive.slim(t, not args.no_titles) for t in cloud.fetch_tasks(token, args.region)) if r]
            merged = archive.merge(records, fresh, titles=not args.no_titles)
            log(f"{args.archive}: {len(merged)} prints ({len(merged) - len(records)} new, {len(fresh)} in the cloud)")
            records = merged
            archive.save(args.archive, records)

    days = stats.aggregate(records, tz)
    if args.svg:
        root, ext = os.path.splitext(args.svg)
        for theme, path in (("auto", args.svg), ("light", f"{root}-light{ext}"), ("dark", f"{root}-dark{ext}")):
            write(path, svg.render(days, end, args.metric, args.colors, theme, strip=args.strip, palette=args.palette))
    summary = text.render(days, end, args.metric)
    if args.text:
        write(args.text, summary)
    if args.gist:
        gist_token = os.environ.get("GIST_TOKEN")
        if not gist_token:
            sys.exit("Set GIST_TOKEN: a GitHub token with the gist scope")
        gist.update(args.gist, gist_token, args.gist_title, summary)
        log(f"updated gist {args.gist}")


def write(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    log(f"wrote {path}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="print-heatmap", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="sign in with an emailed code and get BAMBU_TOKEN")
    login.add_argument("--email")
    login.add_argument("--region", choices=cloud.HOSTS, default="global")
    login.add_argument("--repo", help="OWNER/REPO: store the token as a secret there with the GitHub CLI")
    login.add_argument("--secret", default="BAMBU_TOKEN", help="secret name (default BAMBU_TOKEN)")
    login.set_defaults(func=cmd_login)

    up = sub.add_parser("update", help="fetch print history, update the archive, render")
    source = up.add_mutually_exclusive_group()
    source.add_argument("--offline", action="store_true", help="render the archive without fetching")
    source.add_argument("--demo", action="store_true", help="render generated sample data")
    up.add_argument("--archive", default="prints.json", help="print archive (default prints.json)")
    up.add_argument("--svg", help="heatmap path; -light and -dark variants are written next to it")
    up.add_argument("--text", help="text summary path")
    up.add_argument("--gist", metavar="ID", help="write the text summary into this gist (needs GIST_TOKEN)")
    up.add_argument("--gist-title", default=text.TITLE)
    up.add_argument("--metric", choices=stats.METRICS, default="hours")
    up.add_argument("--colors", choices=["activity", "filament"], default="activity",
                    help="activity: palette shade per day; filament: each day in its main filament colour")
    up.add_argument("--palette", choices=svg.PALETTES, default="orange", help="activity colours (default orange)")
    up.add_argument("--strip", action=argparse.BooleanOptionalAction, default=True,
                    help="weekly filament colour strip under the grid (default: on)")
    up.add_argument("--timezone", help="IANA name for day boundaries, e.g. Europe/Berlin (default: local)")
    up.add_argument("--no-titles", action="store_true", help="keep model names out of the archive")
    up.add_argument("--region", choices=cloud.HOSTS, default="global")
    up.add_argument("--end", type=date.fromisoformat, help="last day of the chart (default: today)")
    up.set_defaults(func=cmd_update)

    args = p.parse_args(argv)
    if args.command == "update" and not (args.svg or args.text or args.gist):
        args.svg = "print-heatmap.svg"
    try:
        args.func(args)
    except (cloud.CloudError, gist.GistError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
