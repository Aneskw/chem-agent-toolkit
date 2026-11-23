import hashlib, json, pathlib, urllib.request, time
root=pathlib.Path('/opt/localretro/src')
manifest=json.loads(pathlib.Path('/opt/localretro/source-manifest.json').read_text())
for name, expected in manifest.items():
    url='https://raw.githubusercontent.com/kaist-amsg/LocalRetro/eba83e72efabeb854fec86c865e8743c295a8a1e/'+name
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data=response.read()
            assert hashlib.sha256(data).hexdigest()==expected, name
            break
        except Exception:
            if attempt==2: raise
            time.sleep(2)
    target=root/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
p=root/'preprocessing/Run_preprocessing.py'
s=p.read_text()
for old,new in [
 ('train_valid.append(val_valid, ignore_index=True)', 'pd.concat([train_valid, val_valid], ignore_index=True)'),
 ('all_valid.append(test_valid, ignore_index=True)', 'pd.concat([all_valid, test_valid], ignore_index=True)')]:
    assert s.count(old)==1, old
    s=s.replace(old,new)
p.write_text(s)
installed={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in manifest}
pathlib.Path('/opt/localretro/installed-manifest.json').write_text(json.dumps(installed,sort_keys=True))
for name in ['data/saved_graphs','models','outputs/raw_prediction','outputs/decoded_prediction','outputs/decoded_prediction_class']:
    (root/name).mkdir(parents=True,exist_ok=True)
pathlib.Path('/opt/localretro/VERSION').write_text('eba83e72efabeb854fec86c865e8743c295a8a1e')
