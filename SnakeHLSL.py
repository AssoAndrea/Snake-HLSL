import copy
import ctypes
import random
import struct

import glfw
import compushady
import compushady.formats
import compushady.config
from compushady.shaders import hlsl
from compushady import Swapchain, Buffer


def take_input():
    global add_tile
    if glfw.get_key(window, glfw.KEY_W) and direction != [0, 1]:
        return [0, -1]
    if glfw.get_key(window, glfw.KEY_S) and direction != [0, -1]:
        return [0, 1]
    if glfw.get_key(window, glfw.KEY_A) and direction != [1, 0]:
        return [-1, 0]
    if glfw.get_key(window, glfw.KEY_D) and direction != [-1, 0]:
        return [1, 0]
    if glfw.get_key(window, glfw.KEY_SPACE) and direction != [0, 1]:
        add_tile = True
    return direction


def pack_array(in_arr):
    complete_buffer = bytes(0)
    for item in in_arr:
        buff = struct.pack('8i', *item)
        complete_buffer += buff
    return complete_buffer


def check_collision():
    global power_up
    global add_tile
    head = tiles[-2]
    if head[0] == power_up[0] and head[1] == power_up[1]:
        new_position = random_power_up()
        power_up[0] = new_position[0]
        power_up[1] = new_position[1]
        add_tile = True
        return 2
    return 0


def random_power_up():
    rx = random.randint(0, 512 // 20 * 20)
    rx = rx // 20 * 20
    ry = random.randint(0, 512 // 20 * 20)
    ry = ry // 20 * 20
    print("----PU----", rx,"/",ry)
    return [rx, ry]


def move_snake():
    global add_tile
    global color_staging
    global color_buffer
    global compute
    global target
    new_pos = [0, 0]
    new_pos[0] = tiles[-2][0] + 20 * direction[0]
    new_pos[1] = tiles[-2][1] + 20 * direction[1]
    tiles[0][0] = new_pos[0]
    tiles[0][1] = new_pos[1]
    new_head = tiles[0]
    tiles.remove(new_head)
    tiles.insert(len(tiles) - 1, new_head)
    if add_tile:
        add_tile = False
        new_tile = copy.copy(new_head)
        tiles.insert(0, new_tile)
        color_staging = Buffer(8 * 4 * len(tiles), compushady.HEAP_UPLOAD)
        color_buffer = Buffer(color_staging.size, format=compushady.formats.R32G32B32A32_SINT)
        compute = compushady.Compute(shader, srv=[color_buffer], uav=[target])


W = 512
H = 512
tile0 = [20, 20, 20, 20, 1, 0, 0, 1]
tile1 = [40, 20, 20, 20, 1, 0, 0, 1]
tile2 = [60, 20, 20, 20, 1, 0, 0, 1]
tile3 = [80, 20, 20, 20, 1, 0, 0, 1]
tileHead = [100, 20, 20, 20, 1, 0, 0, 1]
random.seed()
random_pos = random_power_up()
power_up = [random_pos[0], random_pos[1], 20, 20, 0, 1, 0, 1]
update_timer = 20
direction = [1, 0]
tiles = [tile0, tile1, tile2, tile3, tileHead, power_up]
add_tile = False

glfw.init()
glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
window = glfw.create_window(W, H, "Game", None, None)

swap = Swapchain(glfw.get_win32_window(window), compushady.formats.B8G8R8A8_UNORM, 3)
target = compushady.Texture2D(W, H, compushady.formats.B8G8R8A8_UNORM)
color_staging = Buffer(8 * 4 * len(tiles), compushady.HEAP_UPLOAD)
color_buffer = Buffer(color_staging.size, format=compushady.formats.R32G32B32A32_SINT)
shader = hlsl.compile("""
struct quad_s
{
    uint4 obj;
    uint4 color;
};
RWTexture2D<float4> target : register(u0);
StructuredBuffer<quad_s> quads : register(t0);

[numthreads(8,8,1)]
void main(int3 tid : SV_DispatchThreadID)
{
    quad_s quad = quads[tid.z];
    if (tid.x > quad.obj[0] + quad.obj[2])
        return;
    if (tid.x < quad.obj[0])
        return;
    if (tid.y < quad.obj[1])
        return;
    if (tid.y > quad.obj[1] + quad.obj[3])
        return;
    target[tid.xy] = float4(quad.color);
}
""")
clear_screen = compushady.Compute(hlsl.compile("""
RWTexture2D<float4> target : register(u0);
[numthreads(8, 8, 1)]
void main(int3 tid : SV_DispatchThreadID)
{
    target[tid.xy] = float4(0, 0, 0, 0);
}
"""), uav=[target])

compute = compushady.Compute(shader, srv=[color_buffer], uav=[target])

timer = update_timer
while not glfw.window_should_close(window):
    glfw.poll_events()
    clear_screen.dispatch(target.width // 8, target.height // 8, 1)
    direction = take_input()
    timer -= 1
    if timer <= 0:
        timer = update_timer
        move_snake()
        check_collision()

    color_staging.upload(pack_array(tiles))
    color_staging.copy_to(color_buffer)
    compute.dispatch(W // 8, H // 8, len(tiles))
    swap.present(target)

glfw.terminate()
