#!/usr/bin/env python3
import importlib.util, json, pathlib, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("pk",ROOT/"automation/persistent/kernel.py")
pk=importlib.util.module_from_spec(spec); spec.loader.exec_module(pk)

ALL={k:True for k in pk.QUALIFIED}
with tempfile.TemporaryDirectory() as td:
    k=pk.Kernel(pathlib.Path(td))
    a=k.commit("r1",ALL,"initial","test",{"fixture":"all-pass"})
    assert a["goal_reached"] and a["status"]=="PROJECT_GOAL_REACHED"
    assert k.marker.exists() and k.verify()==[]

    broken=dict(ALL); broken["device_restart_ok"]=False
    b=k.commit("r1",broken,"fault:restart","test")
    assert not b["goal_reached"] and b["status"]=="DEMOTED"
    assert not k.marker.exists() and b["metrics"]["demotions"]==1 and k.verify()==[]

    c=k.commit("r1",ALL,"recovered:restart","test")
    assert c["goal_reached"] and c["metrics"]["recoveries"]==1 and k.verify()==[]

    # Corruption must be detected, never silently promoted.
    state=k.state
    obj=json.loads(state.read_text()); obj["checks"]["repo_sync"]=False
    state.write_text(json.dumps(obj)+"\n")
    assert "state_hash" in k.verify()

print("persistent_kernel_tests=PASS")
