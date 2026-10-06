"""Blender look development for Chen Ling: anatomical mesh, groom, rig and set.

Runs inside Blender 5.2. The external MB-Lab database stays in the ignored
asset cache; no add-on is installed and no MB-Lab Python code is imported.
"""
from pathlib import Path
import argparse
import json
import math
import random
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from codecinema.audio.performance import Performance
from codecinema.blender import fcurves_of, muted_modifiers


def mesh(name, vertices, faces, material=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    for face in data.polygons:
        face.use_smooth = True
    if material:
        data.materials.append(material)
    return ob


def material(name, color, roughness=.5, metal=0, weave=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metal
    if weave:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 520
        noise.inputs['Detail'].default_value = 2
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .22
        bump.inputs['Distance'].default_value = .00045
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], shader.inputs['Normal'])
        shader.inputs['Sheen Weight'].default_value = .28
    return mat


def texture(mat, filename, socket, *, uv='UVMap', noncolor=False):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image = nodes.new('ShaderNodeTexImage')
    image.image = bpy.data.images.load(str(filename), check_existing=True)
    if noncolor:
        image.image.colorspace_settings.name = 'Non-Color'
    mapping = nodes.new('ShaderNodeUVMap')
    mapping.uv_map = uv
    links.new(mapping.outputs['UV'], image.inputs['Vector'])
    links.new(image.outputs['Color'], socket)
    return image


def skin_material(root):
    mat = material('Chen Ling • skin', (.54, .38, .31), .5)
    shader = mat.node_tree.nodes.get('Principled BSDF')
    image = texture(mat, root/'hum_m_asian_albedo.png', shader.inputs['Base Color'])
    tone = mat.node_tree.nodes.new('ShaderNodeHueSaturation')
    tone.inputs['Saturation'].default_value = .72
    mat.node_tree.links.new(image.outputs['Color'], tone.inputs['Color'])
    mat.node_tree.links.new(tone.outputs['Color'], shader.inputs['Base Color'])
    shader.inputs['Subsurface Weight'].default_value = .08
    shader.inputs['Subsurface Radius'].default_value = (1, .38, .2)
    shader.inputs['Subsurface Scale'].default_value = .006
    shader.inputs['Specular IOR Level'].default_value = .28
    bump = mat.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .24
    bump.inputs['Distance'].default_value = .001
    texture(mat, root/'human_male_bump.png', bump.inputs['Height'], noncolor=True)
    mat.node_tree.links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat


def body_materials(body, root):
    skin = skin_material(root)
    teeth = material('Chen Ling • teeth', (.68, .63, .52), .32)
    texture(teeth, root/'human_male_teeth.png', teeth.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    iris = material('Chen Ling • eyes', (.07, .045, .025), .22)
    sclera = material('Chen Ling • sclera', (.68, .64, .55), .24)
    pupil = material('Chen Ling • pupils', (.002, .002, .002), .1)
    cornea = material('Chen Ling • cornea', (1, 1, 1), .025)
    # A thin transparent reflection layer also works in EEVEE; solid glass
    # refraction darkens this legacy double-shell eye geometry.
    nodes, links = cornea.node_tree.nodes, cornea.node_tree.links
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    reflection = nodes.get('Principled BSDF')
    reflection.inputs['Base Color'].default_value = (.1, .1, .1, 1)
    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = .08
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(reflection.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], nodes.get('Material Output').inputs['Surface'])
    cornea.surface_render_method = 'DITHERED'
    lash = material('Chen Ling • lashes', (.007, .006, .005), .5)
    lash_shader = lash.node_tree.nodes.get('Principled BSDF')
    # The source atlas is RGB: black strands on white, with no alpha channel.
    # Using its image alpha paints a white outline around the entire eyelid.
    image = texture(lash, root/'human_male_eyelash.png', lash_shader.inputs['Alpha'])
    invert = lash.node_tree.nodes.new('ShaderNodeInvert')
    lash.node_tree.links.new(image.outputs['Color'], invert.inputs['Color'])
    lash.node_tree.links.new(invert.outputs['Color'], lash_shader.inputs['Alpha'])
    lash.surface_render_method = 'DITHERED'
    tongue = material('Chen Ling • mouth interior', (.18, .035, .027), .48)
    for i, old in enumerate(list(body.data.materials)):
        name = old.name.lower()
        body.data.materials[i] = (lash if 'eyelash' in name else pupil if 'pupil' in name else
                                  cornea if 'cornea' in name else iris if 'iris' in name else sclera if 'eyes' in name else
                                  teeth if 'teeth' in name else tongue if 'tongue' in name else skin)


def actor(root):
    with bpy.data.libraries.load(str(root/'data/humanoid_library.blend'), link=False) as (src, dst):
        dst.objects = ['MBLab_human_male', 'MBLab_skeleton_base_fk']
    body, rig = dst.objects
    bpy.context.collection.objects.link(body)
    bpy.context.collection.objects.link(rig)
    body.name, rig.name = 'Chen_Ling', 'Chen_Ling_rig'
    vertices = [Vector(v) for v in json.loads((root/'data/vertices/m_as01_verts.json').read_text())]
    morphs = json.loads((root/'data/morphs/m_as01_morphs.json').read_text())
    # A narrow, youthful face; the same sculpt is used in every preview shot.
    for name, weight in [('Jaw_Prominence_max', .16), ('Jaw_ScaleX_min', .16),
                         ('Chin_SizeX_min', .12), ('Chin_Prominence_max', .12),
                         ('Eyes_BagProminence_min', .28), ('Nose_BaseSizeX_min', .15),
                         ('Mouth_LowerlipVolume_min', .23), ('Mouth_UpperlipVolume_min', .12)]:
        for index, x, y, z in morphs.get(name, []):
            vertices[index] += Vector((x, y, z))*weight
    for vertex, position in zip(body.data.vertices, vertices):
        vertex.co = position
    body.data.update()
    joints = json.loads((root/'data/joints/human_male_joints.json').read_text())
    offsets = json.loads((root/'data/joints/human_male_joints_offset.json').read_text())
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in rig.data.edit_bones:
        for end in ('head', 'tail'):
            key = bone.name+'_'+end
            indices = joints.get(key)
            if indices:
                point = sum((vertices[i] for i in indices), Vector())/len(indices)
                point += Vector(offsets.get(key, (0, 0, 0)))
                setattr(bone, end, point)
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.select_set(False)
    groups = json.loads((root/'data/vgroups/human_male_vgroups_base.json').read_text())
    for name, weights in groups.items():
        group = body.vertex_groups.new(name=name)
        for index, weight in weights:
            group.add([index], weight, 'REPLACE')
    body.parent = rig
    modifier = body.modifiers.new('Anatomical deformation', 'ARMATURE')
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    sub = body.modifiers.new('Skin subdivision', 'SUBSURF')
    sub.levels = sub.render_levels = 2
    body_materials(body, root/'data/textures')
    body.shape_key_add(name='Basis', from_mix=False)
    expressions = json.loads((root/'data/expressions_morphs/m_as01_exprs.json').read_text())
    chosen = ('Expressions_mouthOpenHalf_max', 'Expressions_mouthOpenO_max', 'Expressions_mouthSmile_max',
              'Expressions_eyeClosedL_max', 'Expressions_eyeClosedR_max', 'Expressions_browsMidVert_max',
              'Expressions_browSqueezeL_max', 'Expressions_browSqueezeR_max')
    keys = {}
    for name in chosen:
        # Only known, authored morphs; do not invent a geometric mouth opening.
        if name not in expressions:
            continue
        shape = body.shape_key_add(name=name, from_mix=False)
        for index, x, y, z in expressions[name]:
            shape.data[index].co += Vector((x, y, z))
        keys[name] = shape
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return body, rig, keys


def attach(ob, rig, bone):
    # A mesh authored in rig space gets its exact rest-to-pose transformation.
    group = ob.vertex_groups.new(name=bone)
    group.add(list(range(len(ob.data.vertices))), 1, 'REPLACE')
    mod = ob.modifiers.new('Follow performer', 'ARMATURE')
    mod.object = rig
    ob.parent = rig


def garment(rig, body, fps=24):
    cloth = material('Wet crimson opera robe', (.12, .005, .012), .82, weave=True)
    trim = material('Dark crimson collar', (.045, .004, .007), .72, weave=True)
    for mat in (cloth, trim):
        mat.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value = .06
    n = 64
    rings = [(1.13, .19, .155), (.98, .22, .19), (.80, .265, .245),
             (.59, .285, .285), (.38, .30, .30), (.17, .31, .30)]
    vertices = []
    for z, rx, ry in rings:
        for j in range(n):
            angle = j*math.tau/n
            fold = .006*math.sin(angle*11+.6)+.003*math.cos(angle*17+z*2)
            vertices.append(((rx+fold)*math.cos(angle), (ry+fold)*math.sin(angle), z))
    faces = [(i*n+j, (i+1)*n+j, (i+1)*n+(j+1)%n, i*n+(j+1)%n)
             for i in range(len(rings)-1) for j in range(n)]
    robe = mesh('Chen_Ling_robe', vertices, faces, cloth)
    for name in ('pelvis', 'spine01', 'spine02', 'spine03'):
        group = robe.vertex_groups.new(name=name)
        for i, (z, _, _) in enumerate(rings):
            chosen = 'spine03' if z>1.26 else 'spine02' if z>1.10 else 'spine01' if z>1 else 'pelvis'
            if chosen==name:
                group.add(list(range(i*n,(i+1)*n)), 1, 'REPLACE')
    mod = robe.modifiers.new('Robe follows torso', 'ARMATURE');mod.object=rig
    mod = robe.modifiers.new('Cloth subdivision', 'SUBSURF');mod.levels=mod.render_levels=2
    mod = robe.modifiers.new('Cloth thickness', 'SOLIDIFY');mod.thickness=.003
    robe.parent=rig
    robe.shape_key_add(name='Basis', from_mix=False)
    for direction in (-1,1):
        shape=robe.shape_key_add(name='Hem drift '+str(direction), from_mix=False)
        for vertex in shape.data:
            influence=max(0,(1.1-vertex.co.z)/.9)**2
            vertex.co.x+=direction*.028*influence
            vertex.co.y+=direction*.012*influence*math.sin(vertex.co.x*14)
        driver=shape.driver_add('value').driver
        driver.expression=f'.28+.20*sin(frame/{fps}*2.1+{direction*1.3})'
    points=[]
    for z in (1.015,1.065,1.115):
        for j in range(n):
            angle=j*math.tau/n
            fold=.0015*math.sin(angle*11)
            points.append(((.232+fold)*math.cos(angle),(.203+fold)*math.sin(angle),z))
    sash=mesh('Chen_Ling_robe_sash',points,
              [(i*n+j,(i+1)*n+j,(i+1)*n+(j+1)%n,i*n+(j+1)%n) for i in range(2) for j in range(n)],trim)
    attach(sash,rig,'pelvis')
    mod=sash.modifiers.new('Sash smoothing','SUBSURF');mod.levels=mod.render_levels=1
    # Fit the upper garment to the anatomical surface and retain its joint weights.
    allowed=('spine','pelvis','clavicle','upperarm','lowerarm','neck')
    def covered(vertex):
        if vertex.co.z<1.015:return False
        if not vertex.groups:return False
        dominant=max(vertex.groups,key=lambda group:group.weight)
        group=body.vertex_groups[dominant.group].name
        return group.startswith(allowed) and (group!='neck' or vertex.co.z<1.505)
    remap={};points=[];upper_faces=[]
    for face in body.data.polygons:
        if not all(covered(body.data.vertices[i]) for i in face.vertices):continue
        row=[]
        for i in face.vertices:
            if i not in remap:
                remap[i]=len(points)
                vertex=body.data.vertices[i]
                point=vertex.co+vertex.normal*.022
                group=body.vertex_groups[max(vertex.groups,key=lambda g:g.weight).group].name
                if group.startswith(('spine','pelvis','clavicle')):
                    point.y+=.012 if point.y>0 else -.012
                elif group.startswith(('upperarm','lowerarm')):
                    point+=vertex.normal*.012
                points.append(point)
            row.append(remap[i])
        upper_faces.append(row)
    upper=mesh('Chen_Ling_robe_upper',points,upper_faces,cloth)
    groups={group.name:upper.vertex_groups.new(name=group.name) for group in body.vertex_groups}
    for source,destination in remap.items():
        for group in body.data.vertices[source].groups:
            groups[body.vertex_groups[group.group].name].add([destination],group.weight,'REPLACE')
    mod=upper.modifiers.new('Tailored garment deformation','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
    mod=upper.modifiers.new('Garment subdivision','SUBSURF');mod.levels=mod.render_levels=2
    mod=upper.modifiers.new('Garment thickness','SOLIDIFY');mod.thickness=.003
    upper.parent=rig
    # Hide the anatomical surface beneath opaque clothing. Keep the topology
    # and vertex indices intact for the face expressions and skinning.
    hidden=bpy.data.materials.new('Body beneath robe')
    hidden.use_nodes=True
    transparent=hidden.node_tree.nodes.new('ShaderNodeBsdfTransparent')
    hidden.node_tree.links.new(transparent.outputs[0],hidden.node_tree.nodes.get('Material Output').inputs['Surface'])
    hidden.surface_render_method='DITHERED'
    index=len(body.data.materials);body.data.materials.append(hidden)
    def beneath(vertex):
        if not .20<vertex.co.z<1.495 or not vertex.groups:return False
        dominant=max(vertex.groups,key=lambda g:g.weight)
        return body.vertex_groups[dominant.group].name.startswith(allowed+('thigh','calf'))
    for face in body.data.polygons:
        if all(beneath(body.data.vertices[i]) for i in face.vertices):face.material_index=index
    # Sew the cross collar onto the garment surface, with no detached straps.
    from mathutils.bvhtree import BVHTree
    surface=BVHTree.FromPolygons([v.co for v in upper.data.vertices],
                                [p.vertices[:] for p in upper.data.polygons])
    for side in (-1,1):
        points=[]
        for i in range(16):
            u=i/15;z=1.465-u*.21;x=side*.062*(1-u)
            for xx in (x-.009,x+.009):
                position,normal,_,_=surface.ray_cast(Vector((xx,-.5,z)),Vector((0,1,0)))
                if position is None:
                    position,normal,_,_=surface.find_nearest(Vector((xx,-.15,z)))
                points.append(position+normal*.003)
        collar=mesh('Robe cross collar '+str(side),points,
                    [(i*2,i*2+1,i*2+3,i*2+2) for i in range(15)],trim)
        attach(collar,rig,'spine03')
        mod=collar.modifiers.new('Collar thickness','SOLIDIFY');mod.thickness=.003


def groom(rig, body):
    """Fine swept black strands with a soft, irregular fringe; no polygon spikes."""
    rng=random.Random(731)
    mat=material('Wet black hair',(.003,.002,.0018),.48)
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Anisotropic'].default_value=.55
    shader.inputs['Coat Weight'].default_value=.015
    shader.inputs['Specular IOR Level'].default_value=.19
    # Root strands on the actual scalp surface, rather than on a guessed ellipsoid.
    polygons=[p for p in body.data.polygons
              if p.center.z>1.678 or (p.center.z>1.64 and p.center.y>.018)]
    scalp_vertices=[];scalp_faces=[];remap={}
    for face in polygons:
        indices=[]
        for index in face.vertices:
            if index not in remap:
                remap[index]=len(scalp_vertices)
                vertex=body.data.vertices[index]
                scalp_vertices.append(vertex.co+vertex.normal*.004)
            indices.append(remap[index])
        scalp_faces.append(indices)
    cap=mesh('Chen_Ling_scalp',scalp_vertices,scalp_faces,mat)
    attach(cap,rig,'head')
    sub=cap.modifiers.new('Scalp smoothing','SUBSURF');sub.levels=sub.render_levels=1
    data=bpy.data.curves.new('Chen_Ling_groom','CURVE')
    data.dimensions='3D';data.resolution_u=2;data.bevel_depth=.00032;data.bevel_resolution=1
    for i in range(4000):
        face=rng.choice(polygons)
        a,b,c=[body.data.vertices[j].co for j in face.vertices[:3]]
        u,v=rng.random(),rng.random()
        if u+v>1:u,v=1-u,1-v
        root=a+(b-a)*u+(c-a)*v+face.normal*.005
        direction=Vector((-.022,-.014,-.018))
        drift=(direction-face.normal*direction.dot(face.normal))*rng.uniform(.7,1.5)
        strand=data.splines.new('POLY');strand.points.add(6)
        for k,p in enumerate(strand.points):
            t=k/6
            point=root+drift*t+face.normal*math.sin(math.pi*t)*rng.uniform(.006,.010)
            p.co=(*point,1);p.radius=(1-.84*t)*(1+rng.uniform(-.1,.1))
    # Conform damp, side-swept fringe bundles to the actual forehead surface.
    from mathutils.bvhtree import BVHTree
    forehead=[p.vertices[:] for p in body.data.polygons
              if p.center.z>1.64 and 'skin' in body.data.materials[p.material_index].name]
    surface=BVHTree.FromPolygons([v.co for v in body.data.vertices],forehead)
    for guide in range(36):
        x=-.058+guide*.0032
        end_z=1.667+rng.uniform(-.008,.012)+.008*(x/.06)
        start_z=1.733-.023*(x/.07)**2
        for j in range(14):
            strand=data.splines.new('POLY');strand.points.add(8)
            jitter=rng.uniform(-.0014,.0014)
            for k,p in enumerate(strand.points):
                t=k/8
                probe=Vector((x+jitter-.012*math.sin(t*math.pi/2),-.18,
                              start_z+(end_z-start_z)*t))
                nearest,normal,_,_=surface.find_nearest(probe)
                point=nearest+normal*(.006+.004*math.sin(t*math.pi))
                p.co=(*point,1);p.radius=(1-.86*t)
    hair=bpy.data.objects.new('Chen_Ling_hair',data);bpy.context.collection.objects.link(hair)
    data.materials.append(mat)
    # Curves cannot take an Armature modifier: bone parenting preserves rig-space placement.
    rest=rig.data.bones['head'].matrix_local
    hair.parent=rig;hair.parent_type='BONE';hair.parent_bone='head'
    hair.matrix_parent_inverse=(rest @ Matrix.Translation((0,rig.data.bones['head'].length,0))).inverted()
    return hair


def box(name, position, size, mat, bevel=.02):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position)
    ob=bpy.context.object;ob.name=name;ob.scale=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(mat)
    if bevel:
        mod=ob.modifiers.new('Worn edges','BEVEL');mod.width=bevel;mod.segments=2
    return ob


def light(name, position, energy, color, target, size=1):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.color=color;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=position
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
    return ob


def street(fps=24):
    pavement=material('Wet street',(.033,.041,.048),.28)
    shader=pavement.node_tree.nodes.get('Principled BSDF');shader.inputs['Coat Weight'].default_value=.65
    noise=pavement.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=32
    bump=pavement.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.3;bump.inputs['Distance'].default_value=.004
    pavement.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
    pavement.node_tree.links.new(bump.outputs['Normal'],shader.inputs['Normal'])
    box('Rain-soaked road',(0,4,-.06),(8,35,.1),pavement)
    stone=material('Weathered charcoal plaster',(.057,.066,.071),.85)
    noise=stone.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=18
    bump=stone.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.3;bump.inputs['Distance'].default_value=.016
    stone.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
    stone.node_tree.links.new(bump.outputs['Normal'],stone.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
    for side in (-1,1):box('Street curb',(side*2.8,4,.025),(.20,35,.15),stone)
    frame=material('Painted window timber',(.018,.02,.024),.64)
    glow=material('Warm practical windows',(.38,.19,.07),.45)
    glow.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(1,.43,.11,1)
    glow.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.5
    for side in (-1,1):
        for i in range(5):
            y=2+i*5
            box('Street building',(side*4.9,y,2.2),(3.8,4.65,4.4),stone)
            for z in (1.4,3.15):
                for yy in (y-.9,y+.9):
                    box('Window frame',(side*2.98,yy,z),(.12,.85,1.12),frame)
                    box('Window glass',(side*2.90,yy,z),(.06,.65,.88),glow,0)
                    box('Window mullion',(side*2.85,yy,z),(.08,.04,.95),frame,0)
    light('Soft moon',(1,-2,4.8),460,(.65,.78,1),(0,0,1.4),3)
    light('Warm street practical',(-2.5,-1.6,2.7),170,(1,.78,.58),(0,0,1.3),1.6)
    light('Rain rim',(-1.5,3,3.6),320,(.70,.80,1),(0,0,1.3),2.8)
    world=bpy.context.scene.world
    world.use_nodes=True
    world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.12,.18,.28,1)
    world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.25
    drop_mat=material('Rain water',(.2,.25,.3),.08,.35)
    drop=mesh('Rain streak geometry',[(0,0,0),(.0015,0,0),(.008,0,.063),(.0065,0,.063)],[(0,1,2,3)],drop_mat)
    drop.hide_render=True;drop.hide_viewport=True
    rng=random.Random(802)
    for i in range(380):
        streak=bpy.data.objects.new('Rain streak '+str(i),drop.data);bpy.context.collection.objects.link(streak)
        streak.location=(rng.uniform(-3.5,3.5),rng.uniform(-1.8,11),0)
        seed=rng.uniform(0,8)
        streak.driver_add('location',2).driver.expression=f'5-((frame/{fps}*5.4+{seed})%6)'


def aim(rig, name, direction):
    bone=rig.pose.bones[name]
    bpy.context.view_layer.update()
    rest=rig.data.bones[name].matrix_local.to_quaternion()
    rotation=(rest @ Vector((0,1,0))).rotation_difference(Vector(direction).normalized()) @ rest
    bone.matrix=Matrix.LocRotScale(bone.head,rotation,Vector((1,1,1)))


def animate(rig, keys, data):
    scene=bpy.context.scene;fps=data['fps'];n=data['frames'];period=data['gait_period'];speed=data['walk_speed']
    performance=Performance.load(data['performance'])
    walk=data['scene']=='rain_wide'
    # FK hands and independent head timing, with an IK ankle controller per leg.
    controls={}
    for side in ('L','R'):
        foot=rig.pose.bones['foot_'+side]
        target=bpy.data.objects.new('Ankle contact '+side,None);bpy.context.collection.objects.link(target)
        target.location=foot.head
        pole=bpy.data.objects.new('Knee direction '+side,None);bpy.context.collection.objects.link(pole)
        pole.location=(foot.head.x,-1,.65)
        ik=rig.pose.bones['calf_'+side].constraints.new('IK');ik.target=target;ik.pole_target=pole;ik.chain_count=2
        ik.pole_angle=math.pi/2
        target.rotation_euler=rig.data.bones['foot_'+side].matrix_local.to_euler()
        rotation=foot.constraints.new('COPY_ROTATION');rotation.target=target
        controls[side]=(target,pole,foot.head.copy())
        aim(rig,'upperarm_'+side,(.04 if side=='L' else -.04,-.015,-1))
        aim(rig,'lowerarm_'+side,(.01 if side=='L' else -.01,-.10,-1))
    for pb in rig.pose.bones:
        if pb.name.startswith(('index','middle','ring','pinky')):
            pb.rotation_quaternion=Quaternion((1,0,0),.18)
    rests={name:rig.pose.bones[name].rotation_quaternion.copy() for name in ('upperarm_L','upperarm_R','lowerarm_L','lowerarm_R','head','neck','spine03')}
    blink_times=(2.7,6.9,9.3)
    for frame in range(1,n+1):
        t=(frame-1)/fps
        scene.frame_set(frame)
        rig.location=(.008*math.sin(t*2.3),-speed*t if walk else 0,
                      -.035+.006*math.sin(t/period*math.tau*2) if walk else -.014)
        rig.keyframe_insert('location',frame=frame)
        pelvis=rig.pose.bones['pelvis']
        pelvis.location=(.009*math.sin(t*1.8),0,.007*math.sin(t*1.2))
        pelvis.keyframe_insert('location',frame=frame)
        for side,(target,pole,rest) in controls.items():
            if walk:
                offset=0 if side=='L' else .5
                phase=t/period+offset
                cycle=math.floor(phase);u=phase-cycle
                stride=speed*period
                # During stance the target remains fixed in WORLD space.
                swing=max(0,(u-.58)/.42);ease=swing*swing*(3-2*swing)
                target.location=(rest.x,rest.y-stride*(cycle+ease-offset+.22),
                                 rest.z+.065*math.sin(math.pi*swing))
                pole.location.y=rig.location.y-1
            target.keyframe_insert('location',frame=frame);pole.keyframe_insert('location',frame=frame)
        for name,q in rests.items():
            pb=rig.pose.bones[name];pb.rotation_quaternion=q.copy()
            if name=='head':
                angle=.018*math.sin(t*.83)+.015*math.sin(t*1.71+.2)
                pb.rotation_quaternion=q @ Quaternion((0,0,1),angle)
            elif name=='spine03':
                pb.rotation_quaternion=q @ Quaternion((1,0,0),.008*math.sin(t*1.4))
            elif walk and name.startswith('upperarm'):
                sign=1 if name.endswith('L') else -1
                pb.rotation_quaternion=q @ Quaternion((1,0,0),sign*.12*math.sin(t/period*math.tau))
            pb.keyframe_insert('rotation_quaternion',frame=frame)
        mouth=performance.mouth(t,'chen_ling')
        blink=max((math.exp(-((t-at)/.065)**2) for at in blink_times),default=0)
        for name,key in keys.items():
            key.value=(blink if 'eyeClosed' in name else
                       mouth.opening*.42 if 'mouthOpenHalf' in name and mouth.shape!='o' else
                       mouth.opening*.42 if 'mouthOpenO' in name and mouth.shape=='o' else
                       mouth.opening*.18 if 'mouthSmile' in name and mouth.shape=='i' else
                       .16 if 'browsMidVert' in name else .1 if 'browSqueeze' in name else 0)
            key.keyframe_insert('value',frame=frame)
    animated=[rig,*[ob for control in controls.values() for ob in control[:2]]]
    animated.extend({key.id_data for key in keys.values()})
    for ob in animated:
        for curve in fcurves_of(ob):
            for key in curve.keyframe_points:key.interpolation='LINEAR'


def camera(data):
    scene=bpy.context.scene
    camdata=bpy.data.cameras.new('Cinema camera');camdata.lens=85 if data['scene']=='rain_face' else 42
    camdata.sensor_width=36
    cam=bpy.data.objects.new('Cinema camera',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam
    focus=bpy.data.objects.new('Eyes focus',None);bpy.context.collection.objects.link(focus)
    close=data['scene']=='rain_face'
    focus.parent=bpy.data.objects['Chen_Ling_rig']
    focus.location=(0,-.10,1.63) if close else (0,0,1.02)
    camdata.dof.use_dof=True;camdata.dof.focus_object=focus;camdata.dof.aperture_fstop=2.8 if close else 4
    cam.location=(.48,-2.4,1.62) if close else (1.6,-5.6,1.25)
    cam.rotation_euler=(focus.location-cam.location).to_track_quat('-Z','Y').to_euler()
    initial=cam.location.copy()
    for f in (1,data['frames']):
        t=(f-1)/data['fps']
        cam.location=initial+Vector((.05*f/data['frames'],-data['walk_speed']*t if not close else 0,0))
        cam.keyframe_insert('location',frame=f)
    for curve in fcurves_of(cam):
        for key in curve.keyframe_points:key.interpolation='LINEAR'
    constraint=cam.constraints.new('TRACK_TO');constraint.target=focus
    constraint.track_axis='TRACK_NEGATIVE_Z';constraint.up_axis='UP_Y'


def configure(data):
    scene=bpy.context.scene
    scene.render.engine=data['engine']
    scene.render.resolution_x=data['width'];scene.render.resolution_y=data['height'];scene.render.resolution_percentage=100
    scene.render.fps=data['fps'];scene.frame_start=1;scene.frame_end=data['frames']
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.compression=15
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.render.use_motion_blur=True;scene.render.motion_blur_shutter=.4
    if data['engine']=='CYCLES':
        scene.cycles.samples=data['samples'];scene.cycles.use_denoising=True
        scene.cycles.max_bounces=6;scene.cycles.transparent_max_bounces=8
        prefs=bpy.context.preferences.addons['cycles'].preferences
        try:
            prefs.compute_device_type='METAL' if sys.platform=='darwin' else 'CUDA'
            prefs.get_devices()
            gpu=[d for d in prefs.devices if d.type!='CPU']
            if gpu:
                for device in prefs.devices:device.use=device.type!='CPU'
                scene.cycles.device='GPU'
        except (TypeError,RuntimeError):
            scene.cycles.device='CPU'
    else:
        scene.eevee.taa_render_samples=data['samples']
        scene.eevee.use_raytracing=True


def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True)
    options=parser.parse_args(args)
    data=json.loads(Path(options.manifest).read_text())
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    body,rig,keys=actor(Path(data['assets']))
    garment(rig,body,data['fps']);groom(rig,body);street(data['fps'])
    with muted_modifiers(types=('SUBSURF','ARMATURE','SOLIDIFY','BEVEL')):
        animate(rig,keys,data)
    camera(data);configure(data)
    folder=Path(data['directory']);folder.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'scene.blend'))
    frames=[min(data['frames'],round(data.get('at',2.4)*data['fps'])+1)] if data['still'] else range(1,data['frames']+1)
    for frame in frames:
        target=folder/f'{frame:05d}.png'
        if target.is_file() and target.stat().st_size>1000:
            continue
        scene=bpy.context.scene;scene.frame_set(frame);scene.render.filepath=str(folder/f'{frame:05d}.partial.png')
        bpy.ops.render.render(write_still=True)
        Path(scene.render.filepath).replace(target)
        if frame%24==0 or data['still']:print(f'BLENDER_FRAME {frame}/{data["frames"]}',flush=True)


if __name__=='__main__':
    main()
