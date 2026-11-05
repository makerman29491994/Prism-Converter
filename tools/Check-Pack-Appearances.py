"""Pack-independent controller associations, variants, folders and boundaries."""
import json,sys,tempfile,zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path('src').resolve()))
from PrismConverter import ModelSource,match_texture,build_model,batch_convert
from PrismConverterUI import Converter

with tempfile.TemporaryDirectory(dir='work',prefix='appearances-') as tmp:
    root=Path(tmp)
    def write(name,data):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
    def png(name,color):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);Image.new('RGBA',(16,16),color).save(p)
    def geo(name,identifier):
        write(name,{'minecraft:geometry':[{'description':{'identifier':identifier,'texture_width':16,'texture_height':16},'bones':[{'name':'base','cubes':[{'origin':[0,0,0],'size':[2,2,2],'uv':[0,0]}]}]}]})
    def entity(name,geometries,textures,controller):
        write(name,{'minecraft:client_entity':{'description':{'geometry':geometries,'textures':textures,'render_controllers':[controller]}}})
    geo('models/creatures/fox/fox.geo.json','geometry.fox')
    entity('entity/fox.entity.json',{'default':'geometry.fox'}, {'default':'textures/fox_wrong','winter':'textures/fox_snow','summer':'textures/fox_red'},'controller.render.fox')
    for name,color in [('fox_wrong','blue'),('fox_snow','white'),('fox_red','red')]:png(f'textures/{name}.png',color)
    write('render_controllers/fox.json',{'render_controllers':{'controller.render.fox':{
        'geometry':'Geometry.default','arrays':{'textures':{'Array.skins':['Texture.winter','Texture.summer']}},'textures':['Array.skins[query.variant]']}}})
    source=ModelSource(root/'models/creatures/fox/fox.geo.json')
    assert len(source.models)==2
    assert {r['variant'] for r in source.models}=={'winter','summer'}
    for i,r in enumerate(source.models):
        expected='textures/fox_snow.png' if r['variant']=='winter' else 'textures/fox_red.png'
        assert match_texture(source,i)['texture']==expected
        assert r['variant'] in Converter.model_label(r)
        build_model(source,i)
    report=batch_convert(source,root/'exports');assert report['exported']==2
    # Geometry and texture arrays sharing an index are paired, not cross-matched.
    geo('models/animals/cub.geo.json','geometry.cub');geo('models/animals/adult.geo.json','geometry.adult')
    entity('entity/animal.json',{'cub':'geometry.cub','adult':'geometry.adult'}, {'small':'textures/fox_snow','big':'textures/fox_red'},'controller.render.animal')
    write('render_controllers/animal.json',{'render_controllers':{'controller.render.animal':{
        'geometry':'Array.shapes[q.variant]','arrays':{'geometries':{'Array.shapes':['Geometry.cub','Geometry.adult']},'textures':{'Array.skins':['Texture.small','Texture.big']}},'textures':['Array.skins[q.variant]']}}})
    for name,texture in [('cub','fox_snow'),('adult','fox_red')]:
        source=ModelSource(root/f'models/animals/{name}.geo.json')
        assert len(source.models)==1 and match_texture(source,0)['texture']==f'textures/{texture}.png'
    # Layered or unknown game-time logic must not quietly select the default.
    geo('models/layered.geo.json','geometry.layered')
    entity('entity/layered.json',{'default':'geometry.layered'},{'base':'textures/fox_snow','overlay':'textures/fox_red'},'controller.render.layered')
    write('render_controllers/layers.json',{'render_controllers':{'controller.render.layered':{'geometry':'Geometry.default','textures':['Texture.base','Texture.overlay']}}})
    assert match_texture(ModelSource(root/'models/layered.geo.json'),0)['status']=='ambiguous'
    # Same basename, different objects; full object-folder context resolves it.
    geo('models/entity/robot/body.geo.json','geometry.robot_body')
    png('textures/entity/robot/body.png','green');png('textures/entity/chair/body.png','brown')
    assert match_texture(ModelSource(root/'models/entity/robot/body.geo.json'),0)['texture']=='textures/entity/robot/body.png'
    # A missing authoritative reference cannot be substituted by a nearby icon.
    geo('models/missing.geo.json','geometry.missing');png('textures/missing.png','red')
    entity('entity/missing.json',{'default':'geometry.missing'},{'default':'textures/not_in_pack'},'controller.render.default')
    assert match_texture(ModelSource(root/'models/missing.geo.json'),0)['status']=='missing'
    # Blockbench namespace references also work when bundled in a multi-pack ZIP.
    png('assets/custom/textures/creatures/bee.png','yellow')
    write('models/bee.bbmodel',{'name':'bee','resolution':{'width':16,'height':16},
        'textures':[{'path':'custom:creatures/bee'}],
        'elements':[{'uuid':'cube','from':[0,0,0],'to':[2,2,2],
            'faces':{'north':{'texture':0,'uv':[0,0,2,2]}}}], 'outliner':['cube']})
    source=ModelSource(root/'models/bee.bbmodel')
    assert match_texture(source,0)['status']=='embedded';build_model(source,0)
    # ZIPs with two packs must preserve controller and fallback texture scope.
    archive=root/'packs.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for prefix in ('A','B'):
            for asset in root.rglob('*'):
                if asset.is_file() and asset.suffix in ('.png','.json','.bbmodel') and 'exports' not in asset.parts:
                    z.write(asset,f'{prefix}/{asset.relative_to(root).as_posix()}')
    source=ModelSource(archive)
    for i,r in enumerate(source.models):
        match=match_texture(source,i)
        if match['status']=='matched':assert match['texture'].split('/')[0]==r['file'].split('/')[0]
    fox=[(i,r) for i,r in enumerate(source.models) if r.get('variant') in ('winter','summer')]
    assert len(fox)==4
    bees=[(i,r) for i,r in enumerate(source.models) if r['kind']=='bbmodel']
    assert len(bees)==2
    for i,r in bees:
        assert match_texture(source,i)['status']=='embedded';build_model(source,i)
print('Pack appearances passed: texture arrays, paired geometry variants, previews/batch, missing/layered references, folder context and ZIP pack isolation.')
