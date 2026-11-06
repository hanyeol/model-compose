from enum import Enum

class Model3DFormat(str, Enum):
    GLB  = "glb"
    GLTF = "gltf"
    OBJ  = "obj"
    PLY  = "ply"
    FBX  = "fbx"
    STL  = "stl"
