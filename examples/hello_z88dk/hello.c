#include <sms.h>
#include <stdio.h>
#include <intrinsic.h>
#include <stdint.h>
#include "SMSlib.h"

extern const uint8_t spritePalette[];
extern const uint8_t shipSprite[];
extern const uint8_t leftShip[];
extern const uint8_t rightShip[];

static const uint8_t shipMetaSprite[] = {8, 0, 0x00,
                                         16, 0, 0x02,
                                         0, 16, 0x04,
                                         8, 16, 0x06,
                                         16, 16, 0x08,
                                         24, 16, 0x0a,
                                         METASPRITE_END};
static const uint8_t shipTilesCenter[] = {0x00, 0x02, 0x04, 0x06, 0x08, 0x0a, METASPRITE_END};
static const uint8_t shipTilesLeft[] = {0x0c, 0x0e, 0x10, 0x12, 0x14, 0x16, METASPRITE_END};
static const uint8_t shipTilesRight[] = {0x18, 0x1a, 0x1c, 0x1e, 0x20, 0x22, METASPRITE_END};

#define SPRITE_WIDTH 32
#define SPRITE_HEIGHT 32

#ifdef TARGET_GG
// Game Gear visible screen: 160x144
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 144
// GG tilemap window is offset 6 columns right and 3 rows down from the VDP map origin
#define TEXT_X_OFFSET 6
#define TEXT_Y_OFFSET 3
#else
// Master System screen: 256x192
#define SCREEN_WIDTH 256
#define SCREEN_HEIGHT 192
#define TEXT_X_OFFSET 0
#define TEXT_Y_OFFSET 0
#endif

// Pixel offsets for the visible area (tile offsets * 8)
#define SCREEN_X_OFFSET (TEXT_X_OFFSET * 8)
#define SCREEN_Y_OFFSET (TEXT_Y_OFFSET * 8)

#ifdef TARGET_GG
// GG palettes are 16 entries of 12-bit color (format: ----BBBBGGGGRRRR, 4 bits per channel).
// These mirror the SMS palette below, scaled from 2-bit (0-3) to 4-bit (0-15) per channel.
const int16_t pal1[] = {
    RGB(0, 0, 0), RGB(15, 0, 0), RGB(0, 10, 0), RGB(0, 10, 10),
    RGB(10, 0, 0), RGB(10, 0, 10), RGB(10, 10, 0), RGB(10, 10, 10),
    RGB(5, 5, 5), RGB(5, 5, 15), RGB(5, 15, 5), RGB(5, 15, 15),
    RGB(15, 5, 5), RGB(15, 5, 15), RGB(15, 15, 5), RGB(15, 15, 15)};
#else
// SMS palettes are 16 entries of 6-bit colour (format: --BBGGRR, 2 bits per channel).
// pal1 is loaded as the BG palette; spritePalette (from the asset converter) as the sprite palette.
const uint8_t pal1[] = {0x00, 0x03, 0x08, 0x28, 0x02, 0x22, 0x0A, 0x2A,
                        0x15, 0x35, 0x1D, 0x3D, 0x17, 0x37, 0x1F, 0x3F};
#endif

extern uint8_t SpriteNextFree;

void main(void)
{
    static uint8_t spriteX = SCREEN_X_OFFSET + (SCREEN_WIDTH - SPRITE_WIDTH) / 2;
    static uint8_t spriteY = SCREEN_Y_OFFSET + (SCREEN_HEIGHT - SPRITE_HEIGHT) / 2;
    static uint8_t shipSpriteID;

    SMS_init();
    SMS_setSpriteMode(SPRITEMODE_TALL);

    // Link z88dk interrupts to SMSlib ISRs.
    // SMS_isr handles the vblank (raster) interrupt; SMS_nmi_isr handles the Pause button (NMI).
    add_raster_int(SMS_isr);
#ifndef TARGET_GG
    // GG has no NMI/Pause button.
    add_pause_int(SMS_nmi_isr);
#endif

    // Use tiles 256-511 for sprites, leaving tiles 0-255 for backgrounds/text.
    SMS_useFirstHalfTilesforSprites(0);
    // Load the built-in font into VRAM, mapping tile indices to ASCII codes (tile = char - 32).
    SMS_autoSetUpTextRenderer();

#ifdef TARGET_GG
    GG_loadBGPalette(pal1);
    GG_loadSpritePalette(spritePalette);
    SMS_loadTiles(shipSprite, 0x100, 32 * 12);
    SMS_loadTiles(leftShip, 0x10c, 32 * 12);
    SMS_loadTiles(rightShip, 0x118, 32 * 12);
#else
    SMS_loadBGPalette(pal1);
    SMS_loadSpritePalette(spritePalette);
    SMS_loadTiles(shipSprite, 0x100, 32 * 12);
    SMS_loadTiles(leftShip, 0x10c, 32 * 12);
    SMS_loadTiles(rightShip, 0x118, 32 * 12);
#endif

    SMS_setNextTileatXY(TEXT_X_OFFSET, TEXT_Y_OFFSET + 0);
    printf("Hello world!");

    SMS_setNextTileatXY(TEXT_X_OFFSET, TEXT_Y_OFFSET + 1);
    SMS_print("Is it working?");

    SMS_printatXY(TEXT_X_OFFSET, TEXT_Y_OFFSET + 2, "I hope so.");

    SMS_printatXY(TEXT_X_OFFSET, TEXT_Y_OFFSET + 3, "Use control pad to move sprite.");

#ifndef TARGET_GG
    // VDP type detection is SMS-only.
    SMS_setNextTileatXY(TEXT_X_OFFSET, TEXT_Y_OFFSET + 4);
    printf("VDP type: %s", SMS_VDPType() != VDP_PAL ? "NTSC" : "PAL");
#endif

    shipSpriteID = SpriteNextFree;
    SMS_addMetaSprite(spriteX, spriteY, shipMetaSprite);

    for (;;)
    {
        // static so these retain their values across iterations without using heap allocation.
        static uint16_t keyStatus, lastKey;

        // Halt until the next interrupt (vblank at ~60 Hz), synchronising the loop to the display.
        __asm__("halt");

        // Copy the sprite buffer to the Sprite Attribute Table in VRAM.
        // Must be called during vblank (right after halt) to avoid tearing.
        SMS_copySpritestoSAT();

        keyStatus = SMS_getKeysStatus();

#ifndef TARGET_GG
        // Check for reset pressed (SMS only — GG has no reset button).
        if (keyStatus & RESET_KEY)
        {
            SMS_displayOff();
            SMS_zeroSpritePalette();
            SMS_zeroBGPalette();
            intrinsic_di();
            __asm__("rst $00");
            // Never reach here
        }
#endif

        // Up or Down?
        if ((keyStatus & PORT_A_KEY_UP) && spriteY > SCREEN_Y_OFFSET)
            spriteY -= 2;
        else if ((keyStatus & PORT_A_KEY_DOWN) && spriteY < SCREEN_Y_OFFSET + SCREEN_HEIGHT - SPRITE_HEIGHT)
            spriteY += 2;

        // Left or Right?
        if ((keyStatus & PORT_A_KEY_LEFT) && spriteX > SCREEN_X_OFFSET)
        {
            spriteX -= 2;
            SMS_updateMetaSpriteImage(shipSpriteID, shipTilesLeft);
        }
        else if ((keyStatus & PORT_A_KEY_RIGHT) && spriteX < SCREEN_X_OFFSET + SCREEN_WIDTH - SPRITE_WIDTH)
        {
            spriteX += 2;
            SMS_updateMetaSpriteImage(shipSpriteID, shipTilesRight);
        }
        else
        {
            SMS_updateMetaSpriteImage(shipSpriteID, shipTilesCenter);
        }

        // XOR with the previous frame's status: bits that differ are keys that changed state.
        lastKey ^= keyStatus;

        if (lastKey & PORT_A_KEY_1)
        {
#ifdef TARGET_GG
            if (keyStatus & PORT_A_KEY_1)
                GG_setSpritePaletteColor(1, RGB(15, 15, 15)); // Pressed
            else
                GG_setSpritePaletteColor(1, RGB(15, 0, 0)); // Released
#else
            if (keyStatus & PORT_A_KEY_1)
                SMS_setSpritePaletteColor(1, 0x3f); // Pressed
            else
                SMS_setSpritePaletteColor(1, 0x10); // Released
#endif
        }

        if (lastKey & PORT_A_KEY_2)
        {
#ifdef TARGET_GG
            if (keyStatus & PORT_A_KEY_2)
                GG_setSpritePaletteColor(1, RGB(15, 15, 5)); // Pressed
            else
                GG_setSpritePaletteColor(1, RGB(15, 0, 0)); // Released
#else
            if (keyStatus & PORT_A_KEY_2)
                SMS_setSpritePaletteColor(1, 0x0f); // Pressed
            else
                SMS_setSpritePaletteColor(1, 0x10); // Released
#endif
        }

        lastKey = keyStatus;

#ifndef TARGET_GG
        // GG has no Pause/NMI button.
        if (SMS_queryPauseRequested())
        {
            // 6 tiles × 2 bytes per tilemap entry = 12 bytes needed to save the area.
            static unsigned char buffer[12];

            SMS_resetPauseRequest();

            // Save the 6×1 tile area where "PAUSED" will be printed, then restore it on unpause.
            SMS_saveTileMapArea(13, 12, buffer, 6, 1);
            SMS_printatXYwithAttr(13, 12, "PAUSED", TILE_PRIORITY);

            // Loop until pause is requested again (unpause)
            while (!SMS_queryPauseRequested())
                __asm__("halt");

            SMS_resetPauseRequest();
            SMS_loadTileMapArea(13, 12, buffer, 6, 1);
        }
#endif
        SMS_updateMetaSpritePosition(shipSpriteID, spriteX, spriteY, shipMetaSprite);
    }
}
