"""Local CLI client. Secrets and its small config stay in the current workspace."""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .client import APIError, BrainAPIClient


def _config_path():
    base = Path(os.environ.get("BRAIN_CONFIG_DIR", Path.cwd() / ".brain")).resolve()
    if not base.is_relative_to(Path.cwd().resolve()):
        raise ValueError("CLI config must remain inside the current workspace")
    return base / "config.json"


def _load_config():
    path = _config_path()
    try:
        if path.is_symlink(): raise ValueError("CLI config may not be a symlink")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict): raise ValueError("invalid CLI config")
        return obj
    except FileNotFoundError:
        return {}


def _save_config(config):
    path = _config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd,tmp_name=tempfile.mkstemp(prefix=".config-",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
            stream.flush();os.fsync(stream.fileno())
        os.replace(tmp_name,path)
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def _client(config, api=None):
    token = os.environ.get("BRAIN_TOKEN", config.get("token", ""))
    return BrainAPIClient(api or os.environ.get("BRAIN_API_URL") or config.get("api_url", "http://127.0.0.1:8080"), token, connection="cli")


def _bytes(resource):
    value = resource.get("content")
    if isinstance(value, dict) and "content_base64" in value:
        return base64.b64decode(value["content_base64"], validate=True)
    if isinstance(value, str): return value.encode("utf-8")
    return b""


def _workspace(args, config):
    return args.workspace or os.environ.get("BRAIN_WORKSPACE_ID") or config.get("workspace_id")


def _session(args, config):
    return args.session or os.environ.get("BRAIN_SESSION_ID") or config.get("session_id")


def _parser():
    p=argparse.ArgumentParser(prog="brain",description="Company Brain workspace client")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--api-url");p.add_argument("--workspace");p.add_argument("--session")
    sub=p.add_subparsers(dest="command",required=True)
    login=sub.add_parser("login");login.add_argument("--api-url",dest="login_api",default=None)
    sub.add_parser("workspaces")
    ls=sub.add_parser("ls");ls.add_argument("path",nargs="?",default="")
    cat=sub.add_parser("cat");cat.add_argument("path")
    search=sub.add_parser("search");search.add_argument("query")
    hist=sub.add_parser("history");hist.add_argument("--session-events",action="store_true")
    sess=sub.add_parser("session");ss=sess.add_subparsers(dest="session_action",required=True)
    start=ss.add_parser("start");start.add_argument("--workspace-id");start.add_argument("--agent",default="cli")
    resume=ss.add_parser("resume");resume.add_argument("session_id")
    ss.add_parser("commit");ss.add_parser("close")
    run=sub.add_parser("run");run.add_argument("script",type=Path)
    files=sub.add_parser("files");fs=files.add_subparsers(dest="files_action",required=True)
    put=fs.add_parser("write");put.add_argument("path");put.add_argument("file",type=Path,nargs="?");put.add_argument("--commit",action="store_true")
    delete=fs.add_parser("delete");delete.add_argument("path");delete.add_argument("--commit",action="store_true")
    tools=sub.add_parser("tools");ts=tools.add_subparsers(dest="tools_action",required=True)
    ts.add_parser("list")
    tsearch=ts.add_parser("search");tsearch.add_argument("query")
    tdetail=ts.add_parser("detail");tdetail.add_argument("name")
    tcall=ts.add_parser("call");tcall.add_argument("name");tcall.add_argument("arguments",nargs="?",default="{}")
    sub.add_parser("help")
    return p


def main(argv=None):
    args=_parser().parse_args(argv)
    try:
        config=_load_config()
        if args.command=="login":
            config["api_url"]=args.login_api or args.api_url or os.environ.get("BRAIN_API_URL") or "http://127.0.0.1:8080"
            config["token"]=getpass.getpass("Company Brain token: ").strip()
            if not config["token"]: raise ValueError("token cannot be empty")
            _save_config(config);print("Saved local credentials in .brain/config.json");return 0
        api=_client(config,args.api_url)
        wid=_workspace(args,config);sid=_session(args,config)
        if not api.token and not args.session: sid=None
        if wid and sid and args.command not in ("session",):
            session_info=api.request("GET",f"/v1/sessions/{api.segment(sid)}")
            if session_info.get("workspace_id")!=wid:
                raise ValueError("active session belongs to a different workspace; pass its workspace or start/resume a matching session")
        if args.command=="workspaces":
            print(json.dumps(api.workspaces(),ensure_ascii=False,indent=2));return 0
        if args.command=="session":
            if args.session_action=="start":
                wid=args.workspace_id or wid
                if not wid: raise ValueError("pass --workspace or session start --workspace-id")
                result=api.start_session(wid,args.agent);config.update(workspace_id=wid,session_id=result["id"]);_save_config(config)
            elif args.session_action=="resume":
                result=api.request("POST",f"/v1/sessions/{api.segment(args.session_id)}/resume",{})
                config.update(session_id=args.session_id,workspace_id=result["workspace_id"]);_save_config(config)
            else:
                if not sid: raise ValueError("no active session; run `brain session start`")
                route=f"/v1/sessions/{api.segment(sid)}/"+args.session_action
                result=api.request("POST",route,{"message":"CLI commit"} if args.session_action=="commit" else {})
                if args.session_action=="close":config.pop("session_id",None);_save_config(config)
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=="ls":
            if not wid: raise ValueError("pass --workspace or configure a workspace")
            prefix=args.path.strip("/")
            resources=api.workspace(wid).get("resources",[])
            paths=[x["path"] for x in resources if not prefix or x["path"]==prefix or x["path"].startswith(prefix.rstrip("/")+"/")]
            print("\n".join(paths));return 0
        if args.command=="cat":
            if not wid: raise ValueError("pass --workspace or configure a workspace")
            resource=api.session_resource(sid,args.path) if sid else api.resource(wid,args.path)
            sys.stdout.buffer.write(_bytes(resource));return 0
        if args.command=="search":
            if not wid: raise ValueError("pass --workspace or configure a workspace")
            print(json.dumps(api.search(wid,args.query),ensure_ascii=False,indent=2));return 0
        if args.command=="history":
            if not wid: raise ValueError("pass --workspace or configure a workspace")
            items=api.session_history(sid) if args.session_events and sid else api.changesets(wid)
            print(json.dumps(items,ensure_ascii=False,indent=2));return 0
        if args.command=="run":
            if not sid: raise ValueError("run requires an active session; use `brain session start`")
            script=args.script.read_text(encoding="utf-8")
            result=api.session_call(sid,"brain.execute",{"script":script})
            stdout=result.get("stdout",{});stderr=result.get("stderr",{})
            if isinstance(stdout,dict):sys.stdout.buffer.write(base64.b64decode(stdout.get("content_base64","")))
            if isinstance(stderr,dict):sys.stderr.buffer.write(base64.b64decode(stderr.get("content_base64","")))
            print(json.dumps({"exit_code":result.get("exit_code"),"commit":result.get("commit")},ensure_ascii=False),file=sys.stderr)
            return 0 if result.get("exit_code")==0 else 1
        if args.command=="files":
            if not sid: raise ValueError("file writes require an active session")
            if args.files_action=="write":
                content=(args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read())
                result=api.session_call(sid,"files.write",{"path":args.path,"content":content})
            else:result=api.session_call(sid,"files.delete",{"path":args.path})
            if args.commit:result={"staged":result,"commit":api.request("POST",f"/v1/sessions/{api.segment(sid)}/commit",{"message":"CLI file update"})}
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=="tools":
            if not sid: raise ValueError("tool discovery requires an active session")
            if args.tools_action=="list":result=api.request("GET",f"/v1/sessions/{api.segment(sid)}/tools").get("tools",[])
            elif args.tools_action=="search":result=api.request("GET",f"/v1/sessions/{api.segment(sid)}/tool-search?q={api.segment(args.query)}").get("tools",[])
            elif args.tools_action=="detail":result=api.request("GET",f"/v1/sessions/{api.segment(sid)}/tools/{api.segment(args.name)}")
            else:result=api.session_call(sid,args.name,json.loads(args.arguments))
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=="help":
            if not sid: print("Use `brain session start --workspace-id ID`, then brain ls/cat/search/run.");return 0
            print(json.dumps(api.session_call(sid,"brain.help",{}),ensure_ascii=False,indent=2));return 0
        return 2
    except (APIError,ValueError,OSError,json.JSONDecodeError) as exc:
        print(f"brain: {exc}",file=sys.stderr);return 1


if __name__=="__main__":
    raise SystemExit(main())
