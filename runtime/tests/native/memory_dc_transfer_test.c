/* Regression harness for the real 0000 helper. This mock validates the
 * conversion contract and GL state, not Wine's own convert_bitmapinfo code. */
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
typedef int BOOL, GLint;
typedef unsigned int GLenum;
typedef size_t SIZE_T;
#define FALSE 0
#define BI_RGB 0
typedef struct { unsigned int biSize; int biWidth, biHeight; unsigned short biPlanes, biBitCount;
    unsigned int biCompression, biSizeImage; int biXPelsPerMeter, biYPelsPerMeter;
    unsigned int biClrUsed, biClrImportant; } BITMAPINFOHEADER;
typedef struct { BITMAPINFOHEADER bmiHeader; } BITMAPINFO;
struct bitblt_coords { int width, height; struct { int left, top, right, bottom; } visrect; };
struct opengl_drawable { int draw_fbo, read_fbo; };
enum { GL_UNPACK_ALIGNMENT, GL_PACK_ALIGNMENT, GL_UNPACK_ROW_LENGTH, GL_PACK_ROW_LENGTH,
    GL_UNPACK_SKIP_ROWS, GL_PACK_SKIP_ROWS, GL_UNPACK_SKIP_PIXELS, GL_PACK_SKIP_PIXELS,
    GL_PIXEL_UNPACK_BUFFER, GL_PIXEL_PACK_BUFFER, GL_PIXEL_UNPACK_BUFFER_BINDING,
    GL_PIXEL_PACK_BUFFER_BINDING, GL_TEXTURE_BINDING_2D, GL_DRAW_FRAMEBUFFER,
    GL_READ_FRAMEBUFFER, GL_FRONT_LEFT, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME,
    GL_TEXTURE_2D, GL_BGRA, GL_UNSIGNED_BYTE, GL_STATE_COUNT };
static int state[GL_STATE_COUNT], transfer_count, conversions, fail_conversion;
static unsigned char framebuffer[24];
static void get_integer(GLenum key, GLint *value) { *value = state[key]; }
static void pixel_store(GLenum key, GLint value) { state[key] = value; }
static void bind_buffer(GLenum target, unsigned int value) {
    state[target == GL_PIXEL_UNPACK_BUFFER ? GL_PIXEL_UNPACK_BUFFER_BINDING : GL_PIXEL_PACK_BUFFER_BINDING] = value;
}
static void bind_framebuffer(GLenum target, unsigned int value) { (void)target; (void)value; }
static void attachment(GLenum target, GLenum buffer, GLenum parameter, GLint *value) {
    assert(target == GL_DRAW_FRAMEBUFFER && buffer == GL_FRONT_LEFT);
    assert(parameter == GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME); *value = 17;
}
static void bind_texture(GLenum target, unsigned int value) {
    assert(target == GL_TEXTURE_2D); state[GL_TEXTURE_BINDING_2D] = value;
}
static void select_buffer(GLenum value) { assert(value == GL_FRONT_LEFT); }
static GLenum drawable_buffer_from_buffer(struct opengl_drawable *drawable, GLenum buffer) {
    (void)drawable; return buffer;
}
static void check_transfer(int width, int height, GLenum format, GLenum type, int write) {
    assert(width == 3 && height == 2 && format == GL_BGRA && type == GL_UNSIGNED_BYTE);
    assert(state[write ? GL_UNPACK_ALIGNMENT : GL_PACK_ALIGNMENT] == 4);
    assert(!state[write ? GL_UNPACK_ROW_LENGTH : GL_PACK_ROW_LENGTH]);
    assert(!state[write ? GL_UNPACK_SKIP_ROWS : GL_PACK_SKIP_ROWS]);
    assert(!state[write ? GL_UNPACK_SKIP_PIXELS : GL_PACK_SKIP_PIXELS]);
    assert(!state[write ? GL_PIXEL_UNPACK_BUFFER_BINDING : GL_PIXEL_PACK_BUFFER_BINDING]);
    transfer_count++;
}
static void draw_pixels(int width, int height, GLenum format, GLenum type, const void *data) {
    check_transfer(width, height, format, type, 1); memcpy(framebuffer, data, sizeof(framebuffer));
}
static void texture_pixels(GLenum target, int level, int x, int y, int width, int height,
                           GLenum format, GLenum type, const void *data) {
    assert(target == GL_TEXTURE_2D && !level && !x && !y);
    assert(state[GL_TEXTURE_BINDING_2D] == 17); draw_pixels(width, height, format, type, data);
}
static void read_pixels(int x, int y, int width, int height, GLenum format, GLenum type, void *data) {
    assert(!x && !y); check_transfer(width, height, format, type, 0);
    memcpy(data, framebuffer, sizeof(framebuffer));
}
struct opengl_funcs {
    void (*p_glGetIntegerv)(GLenum, GLint *);
    void (*p_glPixelStorei)(GLenum, GLint);
    void (*p_glBindBuffer)(GLenum, unsigned int);
    void (*p_glBindFramebuffer)(GLenum, unsigned int);
    void (*p_glGetFramebufferAttachmentParameteriv)(GLenum, GLenum, GLenum, GLint *);
    void (*p_glBindTexture)(GLenum, unsigned int);
    void (*p_glTexSubImage2D)(GLenum, int, int, int, int, int, GLenum, GLenum, const void *);
    void (*p_glDrawBuffer)(GLenum);
    void (*p_glReadBuffer)(GLenum);
    void (*p_glDrawPixels)(int, int, GLenum, GLenum, const void *);
    void (*p_glReadPixels)(int, int, int, int, GLenum, GLenum, void *);
};
static int stride(const BITMAPINFO *info) {
    return ((info->bmiHeader.biWidth * info->bmiHeader.biBitCount + 31) / 32) * 4;
}
static int convert_bitmapinfo(const BITMAPINFO *src_info, const void *src_bits,
                             const struct bitblt_coords *coords, const BITMAPINFO *dst_info, void *dst_bits) {
    int width = src_info->bmiHeader.biWidth, height = abs(src_info->bmiHeader.biHeight);
    int src_pixel = src_info->bmiHeader.biBitCount / 8, dst_pixel = dst_info->bmiHeader.biBitCount / 8;
    conversions++;
    if (fail_conversion) return 1;
    assert(coords->width == width && coords->height == height);
    assert(dst_info->bmiHeader.biWidth == width && abs(dst_info->bmiHeader.biHeight) == height);
    for (int y = 0; y < height; ++y) {
        int sy = src_info->bmiHeader.biHeight > 0 ? height - 1 - y : y;
        int dy = dst_info->bmiHeader.biHeight > 0 ? height - 1 - y : y;
        const unsigned char *src = (const unsigned char *)src_bits + sy * stride(src_info);
        unsigned char *dst = (unsigned char *)dst_bits + dy * stride(dst_info);
        for (int x = 0; x < width; ++x) {
            memcpy(dst + x * dst_pixel, src + x * src_pixel, 3);
            if (dst_pixel == 4) dst[x * dst_pixel + 3] = src_pixel == 4 ? src[x * src_pixel + 3] : 255;
        }
    }
    return 0;
}
/* PATCH_HELPER */
int main(void) {
    struct opengl_funcs funcs = {get_integer, pixel_store, bind_buffer, bind_framebuffer,
        attachment, bind_texture, texture_pixels, select_buffer, select_buffer, draw_pixels, read_pixels};
    for (int fbo = 0; fbo < 2; ++fbo)
    for (int top_down = 0; top_down < 2; ++top_down)
    for (int depth = 24; depth <= 32; depth += 8) {
        struct opengl_drawable drawable = {fbo, fbo};
        BITMAPINFO info = {.bmiHeader = {sizeof(BITMAPINFOHEADER), 3, top_down ? -2 : 2, 1, depth, BI_RGB}};
        unsigned char bits[24], original[24];
        int saved[GL_STATE_COUNT];
        memset(bits, 0xa5, sizeof(bits));
        for (int row = 0; row < 2; ++row)
        for (int col = 0; col < 3; ++col)
        for (int component = 0; component < depth / 8; ++component)
            bits[row * stride(&info) + col * depth / 8 + component] = row * 50 + col * 5 + component;
        memcpy(original, bits, sizeof(bits));
        for (int i = 0; i < GL_STATE_COUNT; ++i) state[i] = i + 7;
        memcpy(saved, state, sizeof(state));
        transfer_count = conversions = 0;
        assert(sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 1));
        assert(!memcmp(saved, state, sizeof(state)));
        assert(transfer_count == 1 && conversions == 1);
        /* GL row zero is the bottom row regardless of the input DIB direction. */
        assert(framebuffer[0] == (top_down ? 50 : 0));
        assert(framebuffer[12] == (top_down ? 0 : 50));
        memset(bits, 0xa5, sizeof(bits));
        assert(sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 0));
        assert(!memcmp(saved, state, sizeof(state)));
        assert(!memcmp(original, bits, sizeof(bits)));
        assert(transfer_count == 2 && conversions == 2);
        fail_conversion = 1;
        assert(!sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 1));
        assert(transfer_count == 2 && !memcmp(saved, state, sizeof(state)));
        assert(!sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 0));
        assert(transfer_count == 3 && !memcmp(saved, state, sizeof(state)));
        fail_conversion = 0;
        info.bmiHeader.biHeight = INT_MIN;
        assert(!sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 1));
        info.bmiHeader.biHeight = INT_MAX;
        assert(!sync_bitmap_framebuffer(&funcs, &drawable, &info, bits, 1));
    }
    return 0;
}
