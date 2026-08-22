import json, os, pathlib, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parent
CORE=ROOT/'skynet_core.py'
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ); env['SKYNET_HOME']=td
    subprocess.check_call(['python3',str(CORE),'init'],env=env,stdout=subprocess.DEVNULL)
    out=subprocess.check_output(['python3',str(CORE),'submit','health'],env=env,text=True)
    assert json.loads(out)['job']['type']=='health'
    out=subprocess.check_output(['python3',str(CORE),'work-once'],env=env,text=True)
    assert json.loads(out)['state']=='done'
    out=subprocess.check_output(['python3',str(CORE),'verify-audit'],env=env,text=True)
    assert json.loads(out)['ok'] is True
print('PASS')
