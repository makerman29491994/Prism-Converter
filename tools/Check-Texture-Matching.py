"""Texture lookup handles portable references, compound names and ambiguity."""
import json,sys,tempfile,zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path('src').resolve()))
from PrismConverter import ModelSource,match_texture,build_model

with tempfile.TemporaryDirectory(dir='work',prefix='matching-') as tmp:
    root=Path(tmp)
    def png(name):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGBA',(16,16),(100,200,50,255)).save(p)
    def geo(filename,identifier):
        p=root/filename;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'minecraft:geometry':[{'description':{'identifier':identifier,'texture_width':16,'texture_height':16},
            'bones':[{'name':'root','cubes':[{'origin':[0,0,0],'size':[2,2,2],'uv':[0,0]}]}]}]}))
        return p
    png('textures/alien.rover_diffuse.png')
    p=geo('models/unrelated.geo.json','geometry.alien.rover')
    source=ModelSource(p)
    assert match_texture(source,0)['texture']=='textures/alien.rover_diffuse.png'
    png('textures/alien.rover_albedo.png')
    assert match_texture(ModelSource(p),0)['status']=='ambiguous'
    # A partial word or a numbered alternate is never an automatic match.
    p=geo('models/space_ship.geo.json','geometry.space_ship')
    png('textures/ship.png');png('textures/space_ship_2.png')
    assert match_texture(ModelSource(p),0)['status']=='missing'
    # A portable relative path disambiguates identical basenames and multiple textures.
    png('textures/a/body.png');png('textures/b/body.png')
    bb={'name':'test','resolution':{'width':16,'height':16},'textures':[
        {'name':'body.png','relative_path':'../textures/a/body.png'},
        {'name':'body.png','path':'C:/old/project/textures/b/body.png'}],
        'elements':[{'uuid':'cube','from':[0,0,0],'to':[2,2,2],
                     'faces':{'north':{'texture':0,'uv':[0,0,2,2]},'south':{'texture':1,'uv':[0,0,2,2]}}}],
        'outliner':['cube']}
    p=root/'models/test.bbmodel';p.write_text(json.dumps(bb))
    source=ModelSource(p);assert match_texture(source,0)['status']=='embedded'
    assert build_model(source,0)
    # The same resolution works without extracting a ZIP.
    archive=root/'pack.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for asset in root.rglob('*'):
            if asset.is_file() and asset!=archive:z.write(asset,asset.relative_to(root))
    source=ModelSource(archive)
    index=next(i for i,r in enumerate(source.models) if r['kind']=='bbmodel')
    assert match_texture(source,index)['status']=='embedded'
    assert build_model(source,index)

    # Full filenames outrank a generic/shared identifier, including separators.
    png('textures/armor_iron.png');png('textures/armor.png')
    p=geo('models/armor_iron.geo.json','geometry.armor')
    assert match_texture(ModelSource(p),0)['texture']=='textures/armor_iron.png'
    # Stripped asset packs omit texture bindings but retain full-name colors.
    p=geo('models/colored_body.geo.json','geometry.demo_colored_body')
    for color in ('red','blue'):png(f'textures/colored_body_{color}.png')
    png('textures/colored_body_red_normal.png')
    match=match_texture(ModelSource(p),0)
    assert match['status']=='ambiguous' and match['candidates']==['textures/colored_body_blue.png','textures/colored_body_red.png']
    # Material variants share geometry but retain their own declared texture;
    # item icons with identical basenames must not replace entity textures.
    p=geo('models/example_armor_helmet.geo.json','geometry.example_armor.helmet')
    for material in ('iron','gold','diamond'):
        name=f'example_armor_{material}_helmet'
        png(f'textures/entity/{name}.png');png(f'textures/items/{name}.png')
        attach=root/f'attachables/{name}.json';attach.parent.mkdir(exist_ok=True)
        attach.write_text(json.dumps({'minecraft:attachable':{'description':{
            'geometry':{'default':'geometry.example_armor.helmet'},
            'textures':{'default':f'textures/entity/{name}','enchanted':'textures/misc/glint'}}}}))
    source=ModelSource(p)
    assert len(source.models)==3
    for i,record in enumerate(source.models):
        expected=f'textures/entity/{Path(record["file"]).stem}.png'
        assert match_texture(source,i)['texture']==expected
        assert build_model(source,i)
    source=ModelSource(root/'attachables/example_armor_gold_helmet.json')
    assert len(source.models)==1 and match_texture(source,0)['texture']=='textures/entity/example_armor_gold_helmet.png'
    archive=root/'variants.zip'
    with zipfile.ZipFile(archive,'w') as z:
        # Two packs use identical identifiers, but their own binding paths.
        for prefix in ('pack-a','pack-b'):
            for asset in root.rglob('*'):
                if asset.is_file() and asset.suffix in ('.json','.png'):
                    z.write(asset,f'{prefix}/{asset.relative_to(root).as_posix()}')
    source=ModelSource(archive)
    for i,record in enumerate(source.models):
        if record['file'].endswith('/colored_body.geo.json'):
            match=match_texture(source,i);prefix=record['file'].split('/')[0]
            assert len(match['candidates'])==2 and all(p.startswith(prefix+'/') for p in match['candidates'])
    variants=[(i,r) for i,r in enumerate(source.models) if 'example_armor' in r['file']]
    assert len(variants)==6
    for i,record in variants:
        prefix=record['file'].split('/')[0]
        assert match_texture(source,i)['texture']==f'{prefix}/textures/entity/{Path(record["file"]).stem}.png'
print('Texture matching passed: compound identifiers, naming suffixes, ambiguity, variant protection, relative/stale paths, multi-texture loading and ZIPs.')
