"""Reversed bounds export and preview like their canonical positive-size cubes."""
import copy,itertools,json,sys,tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path('src').resolve()))
from PrismConverter import ModelSource,build_model,convert_model
from PrismPolygonPreview import prepare_source_preview

with tempfile.TemporaryDirectory(dir='work',prefix='reversed-') as tmp:
    root=Path(tmp)
    Image.new('RGBA',(32,32),(150,100,50,255)).save(root/'test.png')
    for face_uv in (False,True):
        uv={'north':{'uv':[1,2],'uv_size':[3,4]}} if face_uv else [0,0]
        for signs in itertools.product((-1,1),repeat=3):
            size=[s*d for s,d in zip(signs,(3,4,2))]
            origin=[10,12,14]
            cube={'origin':origin,'size':size,'uv':uv,'pivot':[2,3,4],'rotation':[10,20,30],'mirror':True,'inflate':.1}
            geometry={'description':{'identifier':'geometry.test','texture_width':32,'texture_height':32},
                      'bones':[{'name':'root','pivot':[2,3,4],'cubes':[cube]}]}
            path=root/'test.geo.json'
            def load():
                path.write_text(json.dumps({'minecraft:geometry':[geometry]}))
                return ModelSource(path)
            source=load();model,atlas,report=build_model(source,0)
            assert prepare_source_preview(source,0)
            assert bool(report['warnings'])==any(s<0 for s in signs)
            cube['origin']=[min(a,a+b) for a,b in zip(origin,size)]
            cube['size']=list(map(abs,size))
            expected,image,_=build_model(load(),0)
            assert model==expected and atlas.tobytes()==image.tobytes()
    # Blockbench reversed endpoints share the same behavior, without mutating input.
    bb={'name':'test','resolution':{'width':32,'height':32},'meta':{'box_uv':True},
        'elements':[{'uuid':'cube','from':[4,5,6],'to':[1,2,3],'uv_offset':[0,0]}],'outliner':['cube']}
    path=root/'test.bbmodel';path.write_text(json.dumps(bb));source=ModelSource(path)
    original=copy.deepcopy(source.models[0]['data'])
    result=convert_model(source,0,root/'export',texture_path=root/'test.png')
    assert result['warnings'] and (root/'export/export.mimodel').is_file()
    assert source.models[0]['data']==original
print('Reversed bounds passed: all axes, box/per-face UVs, pivots, rotations, inflation, preview, export and immutable source.')
