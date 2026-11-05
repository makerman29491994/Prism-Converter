"""Static resource-pack appearance associations; never evaluates Molang."""
import re


def pack_prefix(filename):
    parts=filename.replace('\\','/').split('/')
    at=next((i for i,p in enumerate(parts) if p.casefold() in
        ('models','model','entity','attachables','render_controllers','textures','assets')),None)
    return '/'.join(parts[:at]) if at is not None else ''


def expression_choices(expression,kind,arrays):
    """Return aliases plus their array selector, or None for unknown logic."""
    if not isinstance(expression,str):return None
    expression=expression.strip()
    direct=re.fullmatch(kind+r'\.([\w.-]+)',expression,re.I)
    if direct:return [(direct[1].casefold(),None)]
    array=re.fullmatch(r'(array\.[\w.-]+)\s*\[\s*(.*?)\s*\]',expression,re.I)
    if not array:return None
    if not isinstance(arrays,dict):return None
    entries=next((v for k,v in arrays.items() if k.casefold()==array[1].casefold()),None)
    if not isinstance(entries,list):return None
    selector=array[2].strip().casefold()
    indices=[int(selector)] if selector.isdigit() else range(len(entries))
    result=[]
    for i in indices:
        if i>=len(entries):return None
        choice=expression_choices(entries[i],kind,{})
        if not choice:return None
        result.extend((alias,(selector,i)) for alias,_ in choice)
    return result


def controller_bindings(description,controllers):
    """Resolve direct aliases and array variants, pairing equal array selectors.

    None means the controller is unavailable; callers retain legacy matching.
    Unknown expressions and layered textures remain explicitly unresolved.
    """
    declared=description.get('render_controllers',[])
    if not isinstance(declared,list):return None
    geometries={k.casefold():v for k,v in description.get('geometry',{}).items()}
    textures={k.casefold():v for k,v in description.get('textures',{}).items()}
    results=[];found=False
    for entry in declared:
        names=[entry] if isinstance(entry,str) else list(entry) if isinstance(entry,dict) else []
        for name in names:
            controller=controllers.get(name.casefold())
            if not isinstance(controller,dict):continue
            found=True
            arrays=controller.get('arrays',{})
            if not isinstance(arrays,dict):arrays={}
            gs=expression_choices(controller.get('geometry'),'geometry',arrays.get('geometries',{}))
            layers=controller.get('textures',[])
            ts=expression_choices(layers[0],'texture',arrays.get('textures',{})) if isinstance(layers,list) and len(layers)==1 else None
            if not gs or not ts:
                reason='This appearance uses texture layers or game-time expressions; choose a PNG for a simplified preview.'
                for identifier in geometries.values():results.append((identifier,list(textures.values()),'',reason))
                continue
            for ga,gselector in gs:
                identifier=geometries.get(ga)
                if not isinstance(identifier,str):continue
                compatible=[]
                for ta,tselector in ts:
                    if gselector and tselector and gselector[0]==tselector[0] and gselector[1]!=tselector[1]:continue
                    # Independent dynamic selectors cannot be correlated safely.
                    if len(gs)>1 and len(ts)>1 and gselector and tselector and gselector[0]!=tselector[0]:continue
                    if ta in textures:compatible.append((ta,textures[ta]))
                if not compatible:
                    results.append((identifier,list(textures.values()),'','The texture depends on game-time state; choose a PNG.'))
                else:
                    for alias,path in compatible:
                        results.append((identifier,[path],alias if len(ts)>1 or len(declared)>1 else '',None))
    return results if found else None


def folder_candidates(candidates,model_file):
    """Disambiguate complete-name matches by matching resource-relative folders."""
    prefix=pack_prefix(model_file)
    scoped=[p for p in candidates if pack_prefix(p).casefold()==prefix.casefold()]
    candidates=scoped
    def folder(path):
        parts=path.casefold().replace('\\','/').split('/')[:-1]
        at=next((i for i,p in enumerate(parts) if p in ('models','model','textures')),None)
        parts=parts[at+1:] if at is not None else parts
        if parts and parts[0] in ('entity','entities','item','items','block','blocks'):parts=parts[1:]
        return parts
    target=folder(model_file)
    scores=[]
    for path in candidates:
        other=folder(path);score=0
        for a,b in zip(reversed(target),reversed(other)):
            if a!=b:break
            score+=1
        scores.append((score,path))
    best=max((s for s,_ in scores),default=0)
    return [p for s,p in scores if s==best] if best else candidates
