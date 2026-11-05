"""Texture strips retain complete frames and uniform HD pixel density."""
import hashlib,json,sys,tempfile,zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path('src').resolve()))
from PrismConverter import ModelSource,load_model_textures,build_model,convert_model
from PrismConverterPreview import preview_mesh,render_preview

with tempfile.TemporaryDirectory(dir='work',prefix='texture-frames-') as temporary:
    root=Path(temporary)
    for label,scale,horizontal,per_face in [('vertical',1,False,False),('vertical-hd',2,False,True),('horizontal-hd',2,True,False)]:
        pack=root/label;pack.mkdir()
        frame=Image.new('RGBA',(16*scale,16*scale),(180,80,30,255))
        for y in range(frame.height):
            for x in range(frame.width):frame.putpixel((x,y),(x*6,y*6,60,255))
        sheet=Image.new('RGBA',(frame.width*(2 if horizontal else 1),frame.height*(1 if horizontal else 2)))
        sheet.paste(frame,(0,0));sheet.save(pack/'cake.png')
        original=hashlib.sha256((pack/'cake.png').read_bytes()).digest()
        uv={face:{'uv':[0,0],'uv_size':[4,4]} for face in ('north','south','east','west','up','down')} if per_face else [0,0]
        data={'minecraft:geometry':[{'description':{'identifier':'geometry.cake','texture_width':16,'texture_height':16},
            'bones':[{'name':'root','cubes':[{'origin':[0,0,0],'size':[4,4,4],'uv':uv}]}]}]}
        (pack/'cake.geo.json').write_text(json.dumps(data))
        source=ModelSource(pack)
        selected=load_model_textures(source,0)[0]
        assert selected.size==frame.size and selected.tobytes()==frame.tobytes()
        model,atlas,report=build_model(source,0)
        assert len(report['warnings'])==1 and 'first frame' in report['warnings'][0]
        reference=pack/'reference.png';frame.save(reference)
        expected,expected_atlas,_=build_model(source,0,texture_path=reference)
        assert model==expected and atlas.tobytes()==expected_atlas.tobytes()
        for yaw in (0,45,180):
            assert render_preview(preview_mesh(model,atlas),(240,300),yaw,14).tobytes()==render_preview(preview_mesh(expected,expected_atlas),(240,300),yaw,14).tobytes()
        exported=root/(label+'-export');convert_model(source,0,exported)
        assert json.loads((exported/'conversion.json').read_text())['warnings']==report['warnings']
        assert hashlib.sha256((pack/'cake.png').read_bytes()).digest()==original
        archive=root/(label+'.zip')
        with zipfile.ZipFile(archive,'w') as z:
            z.write(pack/'cake.geo.json','Pack/models/cake.geo.json');z.write(pack/'cake.png','Pack/textures/cake.png')
        assert load_model_textures(ModelSource(archive),0)[0].tobytes()==frame.tobytes()
    # A genuine rectangular HD texture has equal X/Y density, not extra frames.
    data['minecraft:geometry'][0]['description']['texture_height']=8
    (pack/'cake.geo.json').write_text(json.dumps(data))
    Image.new('RGBA',(32,16),'green').save(pack/'cake.png')
    assert load_model_textures(ModelSource(pack),0)[0].size==(32,16)
    # An arbitrary aspect mismatch is not evidence of an integral frame strip.
    data['minecraft:geometry'][0]['description']['texture_height']=16
    (pack/'cake.geo.json').write_text(json.dumps(data))
    Image.new('RGBA',(16,24),'green').save(pack/'cake.png')
    assert load_model_textures(ModelSource(pack),0)[0].size==(16,24)
print('Texture frames passed: vertical/horizontal strips, HD, box/per-face UVs, exact reference previews, export, ZIPs, rectangular textures and unchanged input files.')
