#include <sms.h>
#include <stdio.h>
#include <intrinsic.h>
#include <stdint.h>
#include "SMSlib.h"

extern uint8_t SpriteNextFree;
extern uint8_t SpriteTableY[];
extern uint8_t SpriteTableXN[];
extern const uint8_t spritePalette[];
extern const uint8_t shipSprite[];
extern const uint8_t leftShip[];
extern const uint8_t rightShip[];
extern const uint8_t missile[];

static const uint8_t missileMetaSprite[] = {0, 0, 0x24,
                                            14, 0, 0x24,
                                            METASPRITE_END};
static const uint8_t shipMetaSprite[] = {8, 0, 0x00,
                                         16, 0, 0x02,
                                         0, 16, 0x04,
                                         8, 16, 0x06,
                                         16, 16, 0x08,
                                         24, 16, 0x0a,
                                         METASPRITE_END};
static const uint8_t shipTilesCenter[] = {0x00, 0x02, 0x04, 0x06, 0x08, 0x0a, 0xff};
static const uint8_t shipTilesLeft[] = {0x0c, 0x0e, 0x10, 0x12, 0x14, 0x16, 0xff};
static const uint8_t shipTilesRight[] = {0x18, 0x1a, 0x1c, 0x1e, 0x20, 0x22, 0xff};

#define SPRITE_WIDTH 32
#define SPRITE_HEIGHT 32
#define SHIP_X_SPEED 2
#define SHIP_Y_SPEED 2
#define SHIP_X_SPEED_FAST (SHIP_X_SPEED * 2)
#define SHIP_Y_SPEED_FAST (SHIP_Y_SPEED * 2)
#define DOUBLE_TAP_WINDOW 20
#define MAX_MISSILE 5
#define MISSILE_SPEED 8
#define MAX_FUEL 100
#define FUEL_BURN_NORMAL_FRAMES 60  // 1 fuel per second at 60 Hz
#define FUEL_BURN_DOUBLE_FRAMES 20  // 3 fuel per 60 frames = 3 per second at 60 Hz
#define FUEL_DIGIT_BASE_TILE 0x126  // Start of digit tiles in sprite space
#define FUEL_DIGIT_TILE_STRIDE 2    // Spacing between consecutive digit tiles (reserved space)

#ifdef TARGET_GG
#define SET_FIRE_COLOR_PRESSED() GG_setSpritePaletteColor(1, RGB(15, 15, 15))
#define SET_FIRE_COLOR_RELEASED() GG_setSpritePaletteColor(1, RGB(15, 0, 0))
#else
#define SET_FIRE_COLOR_PRESSED() SMS_setSpritePaletteColor(1, 0x3f)
#define SET_FIRE_COLOR_RELEASED() SMS_setSpritePaletteColor(1, 0x10)
#endif

typedef struct Missile
{
    uint8_t spriteID;
    uint8_t x;
    uint8_t y;
#ifdef TARGET_GG
    uint8_t spawnX;         // screen X at time of firing
    int8_t capturedScrollX; // scrollX at time of firing
    int8_t capturedScrollY; // scrollY at last frame (incremental delta tracking)
#endif
} Missile;

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

// Load digit tiles from the default charset into sprite tile space for fuel display
static void loadDigitTilesToSpriteSpace(void)
{
    // The devkitSMS charset (1bpp monochrome) is loaded by SMS_autoSetUpTextRenderer()
    // Charset starts at ASCII 0x20 (space = 32)
    // Digits '0'-'9' are ASCII 48-57, so they're at indices (48-32)=16 through (57-32)=25
    // Each 1bpp tile is 8 bytes
    // Byte offset for digit '0' = 16 * 8 = 128
    
    extern const unsigned char devkitSMS_font__tiles__1bpp[];
    
    uint8_t digit;
    uint16_t tileIndex;
    
    // Load 10 digit tiles (0-9) from charset into sprite tile space
    // For 8x16 sprites, stride by 2 to skip odd positions: 0x126, 0x128, 0x12A, etc.
    // Each digit tile is 8 bytes and maps to a single tile index in VRAM
    for (digit = 0; digit < 10; digit++)
    {
        tileIndex = FUEL_DIGIT_BASE_TILE + (digit * FUEL_DIGIT_TILE_STRIDE);
        // Load 8x8 digit tile data from the charset to sprite tile space
        SMS_load1bppTiles(&devkitSMS_font__tiles__1bpp[128 + (digit * 8)], tileIndex, 
                          8,
                          0,
                          15);
    }
}

static void updateFuelDisplay(uint8_t fuelAmount, uint8_t sprite0, uint8_t sprite1, uint8_t sprite2)
{
    uint8_t hundreds = fuelAmount / 100;
    uint8_t tens = (fuelAmount % 100) / 10;
    uint8_t units = fuelAmount % 10;
    
    // Use double-spaced tile indices for 8x16 sprites
    SMS_updateSpriteImage(sprite0, FUEL_DIGIT_BASE_TILE + (hundreds * FUEL_DIGIT_TILE_STRIDE));
    SMS_updateSpriteImage(sprite1, FUEL_DIGIT_BASE_TILE + (tens * FUEL_DIGIT_TILE_STRIDE));
    SMS_updateSpriteImage(sprite2, FUEL_DIGIT_BASE_TILE + (units * FUEL_DIGIT_TILE_STRIDE));
}

#ifdef TARGET_GG
static int8_t scrollX = 0;
static int8_t scrollY = 0;

// GG palettes are 16 entries of 12-bit color (format: ----BBBBGGGGRRRR, 4 bits per channel).
// These mirror the SMS palette below, scaled from 2-bit (0-3) to 4-bit (0-15) per channel.
static const int16_t pal1[] = {
    RGB(0, 0, 0), RGB(15, 0, 0), RGB(0, 10, 0), RGB(0, 10, 10),
    RGB(10, 0, 0), RGB(10, 0, 10), RGB(10, 10, 0), RGB(10, 10, 10),
    RGB(5, 5, 5), RGB(5, 5, 15), RGB(5, 15, 5), RGB(5, 15, 15),
    RGB(15, 5, 5), RGB(15, 5, 15), RGB(15, 15, 5), RGB(15, 15, 15)};
#else
// SMS palettes are 16 entries of 6-bit colour (format: --BBGGRR, 2 bits per channel).
// pal1 is loaded as the BG palette; spritePalette (from the asset converter) as the sprite palette.
static const uint8_t pal1[] = {0x00, 0x03, 0x08, 0x28, 0x02, 0x22, 0x0A, 0x2A,
                               0x15, 0x35, 0x1D, 0x3D, 0x17, 0x37, 0x1F, 0x3F};
#endif

#ifdef TARGET_GG
static inline int try_scroll_left(uint8_t speed)
{
    if (scrollX < 0x30)
    {
        scrollX += speed;
        INLINE_SMS_setBGScrollX(scrollX);
        return 1;
    }
    return 0;
}
static inline int try_scroll_right(uint8_t speed)
{
    if (scrollX > -0x30)
    {
        scrollX -= speed;
        INLINE_SMS_setBGScrollX(scrollX);
        return 1;
    }
    return 0;
}
// SMS_setBGScrollY takes unsigned char, but the VDP tilemap is 224px tall (not 256),
// so negative int8_t values must not be cast directly — use modular reduction instead.
#define SET_SCROLL_Y(y) SMS_setBGScrollY((uint8_t)((y) < 0 ? 224 + (y) : (y)))

static inline int try_scroll_up(uint8_t speed)
{
    if (scrollY > -0x18)
    {
        scrollY -= speed;
        SET_SCROLL_Y(scrollY);
        return 1;
    }
    return 0;
}
static inline int try_scroll_down(uint8_t speed)
{
    if (scrollY < 0x18)
    {
        scrollY += speed;
        SET_SCROLL_Y(scrollY);
        return 1;
    }
    return 0;
}
#endif

void main(void)
{
    static uint8_t spriteX = SCREEN_X_OFFSET + (SCREEN_WIDTH - SPRITE_WIDTH) / 2;
    static uint8_t spriteY = SCREEN_Y_OFFSET + (SCREEN_HEIGHT - SPRITE_HEIGHT) / 2;
    static uint8_t shipSpriteID;
    static Missile missiles[MAX_MISSILE];
    static uint8_t freeQueue[MAX_MISSILE];
    static uint8_t freeHead = 0;
    static uint8_t freeTail = 0;
    static uint8_t freeCount = 0;
    static uint8_t i;
    static uint8_t frameCount = 0;
    static uint8_t lastDirectionalTapFrame = 0;
    static uint8_t hasDirectionalTap = 0;
    static uint8_t doubleSpeedMode = 0;
    
    // Fuel system variables
    static uint8_t fuel = MAX_FUEL;
    static uint8_t fuelBurnCounter = 0;
    static uint8_t fuelSpriteID[3];  // Three sprite IDs for hundreds, tens, and units

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
    INLINE_SMS_setBGScrollX(scrollX);
    SET_SCROLL_Y(scrollY);
    GG_loadBGPalette(pal1);
    GG_loadSpritePalette(spritePalette);
    SMS_loadTiles(shipSprite, 0x100, 32 * 12);
    SMS_loadTiles(leftShip, 0x10c, 32 * 12);
    SMS_loadTiles(rightShip, 0x118, 32 * 12);
    SMS_loadTiles(missile, 0x124, 32 * 2);
#else
    SMS_loadBGPalette(pal1);
    SMS_loadSpritePalette(spritePalette);
    SMS_loadTiles(shipSprite, 0x100, 32 * 12);
    SMS_loadTiles(leftShip, 0x10c, 32 * 12);
    SMS_loadTiles(rightShip, 0x118, 32 * 12);
    SMS_loadTiles(missile, 0x124, 32 * 2);
#endif

    // Load digit tiles (0-9) from charset to sprite space
    loadDigitTilesToSpriteSpace();
    
    fuelSpriteID[0] = SMS_reserveSprite();  // Hundreds digit
    fuelSpriteID[1] = SMS_reserveSprite();  // Tens digit
    fuelSpriteID[2] = SMS_reserveSprite();  // Units digit

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

    for (i = 0; i < MAX_MISSILE; i++)
    {
        missiles[i].spriteID = SMS_reserveSprite();
        SMS_updateSpriteImage(missiles[i].spriteID, 0x124);     // missile tile (top half)
        SMS_reserveSprite();                                    // reserve adjacent sprite for bottom half
        SMS_updateSpriteImage(missiles[i].spriteID + 1, 0x124); // missile tile (bottom half)

        missiles[i].y = 0xe0;                                   // Inactive
        freeQueue[i] = i;
        freeCount++;
    }
    // freeTail remains 0, pointing to the head of the free missile queue

    // Initialize fuel sprite positions (bottom right corner, 3-digit display)
#ifdef TARGET_GG
    // Game Gear: 160x144, position at bottom right
    SMS_updateSpritePosition(fuelSpriteID[0], 136, 136);
    SMS_updateSpritePosition(fuelSpriteID[1], 144, 136);
    SMS_updateSpritePosition(fuelSpriteID[2], 152, 136);
#else
    // Master System: 256x192, position at bottom right
    SMS_updateSpritePosition(fuelSpriteID[0], 232, 184);
    SMS_updateSpritePosition(fuelSpriteID[1], 240, 184);
    SMS_updateSpritePosition(fuelSpriteID[2], 248, 184);
#endif

    // Initialize fuel display with current fuel amount
    updateFuelDisplay(fuel, fuelSpriteID[0], fuelSpriteID[1], fuelSpriteID[2]);

    for (;;)
    {
        // static so these retain their values across iterations without using heap allocation.
        static uint16_t keyStatus, lastKey;
        static uint16_t directionalNow, directionalPrev;
        static uint8_t ySpeed, xSpeed;
        static const uint8_t *shipImg;
        static uint8_t fuelBurnFrames;

        // Halt until the next interrupt (vblank at ~60 Hz), synchronising the loop to the display.
        __asm__("halt");
        frameCount++;

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

        directionalNow = (uint16_t)(keyStatus & (PORT_A_KEY_UP | PORT_A_KEY_DOWN | PORT_A_KEY_LEFT | PORT_A_KEY_RIGHT));
        directionalPrev = (uint16_t)(lastKey & (PORT_A_KEY_UP | PORT_A_KEY_DOWN | PORT_A_KEY_LEFT | PORT_A_KEY_RIGHT));

        // Detect a new directional tap on the D-pad as a whole (0 -> any direction).
        if (directionalNow && !directionalPrev)
        {
            if (hasDirectionalTap && (uint8_t)(frameCount - lastDirectionalTapFrame) <= DOUBLE_TAP_WINDOW)
                doubleSpeedMode = 1;
            hasDirectionalTap = 1;
            lastDirectionalTapFrame = frameCount;
        }

        // Exit double-speed mode when no directional input
        if (!directionalNow)
            doubleSpeedMode = 0;

        ySpeed = doubleSpeedMode ? SHIP_Y_SPEED_FAST : SHIP_Y_SPEED;
        xSpeed = doubleSpeedMode ? SHIP_X_SPEED_FAST : SHIP_X_SPEED;

        // Fuel burning logic: fuel burns continuously at normal rate or 3x when double speed
        if (fuel > 0)
        {
            fuelBurnFrames = doubleSpeedMode ? FUEL_BURN_DOUBLE_FRAMES : FUEL_BURN_NORMAL_FRAMES;
            fuelBurnCounter++;
            
            if (fuelBurnCounter >= fuelBurnFrames)
            {
                fuelBurnCounter = 0;
                uint8_t fuelBurn = doubleSpeedMode ? 3 : 1;
                fuel = (fuel >= fuelBurn) ? fuel - fuelBurn : 0;
            }
        }
        
        // Update fuel display
        updateFuelDisplay(fuel, fuelSpriteID[0], fuelSpriteID[1], fuelSpriteID[2]);

        // Movement (Up/Down/Left/Right) - only allowed when fuel > 0
        shipImg = shipTilesCenter;
        if (fuel > 0)
        {
            // Up or Down?
            if (keyStatus & PORT_A_KEY_UP)
            {
                if (spriteY > SCREEN_Y_OFFSET)
                    spriteY = (spriteY - SCREEN_Y_OFFSET >= ySpeed) ? spriteY - ySpeed : SCREEN_Y_OFFSET;
#ifdef TARGET_GG
                else
                    try_scroll_up(ySpeed);
#endif
            }
            else if (keyStatus & PORT_A_KEY_DOWN)
            {
                static uint8_t maxY;
                maxY = (uint8_t)(SCREEN_Y_OFFSET + SCREEN_HEIGHT - SPRITE_HEIGHT);
                if (spriteY < maxY)
                    spriteY = (spriteY + ySpeed <= maxY) ? spriteY + ySpeed : maxY;
#ifdef TARGET_GG
                else
                    try_scroll_down(ySpeed);
#endif
            }

            // Left or Right?
            if (keyStatus & PORT_A_KEY_LEFT)
            {
                if (spriteX > SCREEN_X_OFFSET)
                {
                    spriteX = (spriteX - SCREEN_X_OFFSET >= xSpeed) ? spriteX - xSpeed : SCREEN_X_OFFSET;
                    shipImg = shipTilesLeft;
                }
#ifdef TARGET_GG
                else if (try_scroll_left(xSpeed))
                    shipImg = shipTilesLeft;
#endif
            }
            else if (keyStatus & PORT_A_KEY_RIGHT)
            {
                static uint8_t maxX;

                maxX = (uint8_t)(SCREEN_X_OFFSET + SCREEN_WIDTH - SPRITE_WIDTH);
                if (spriteX < maxX)
                {
                    spriteX = (spriteX + xSpeed <= maxX) ? spriteX + xSpeed : maxX;
                    shipImg = shipTilesRight;
                }
#ifdef TARGET_GG
                else if (try_scroll_right(xSpeed))
                    shipImg = shipTilesRight;
#endif
            }
        }
        SMS_updateMetaSpriteImage(shipSpriteID, shipImg);

        // XOR with the previous frame's status: bits that differ are keys that changed state.
        lastKey ^= keyStatus;

        if (lastKey & PORT_A_KEY_1)
        {
            if (keyStatus & PORT_A_KEY_1)
            {
                SET_FIRE_COLOR_PRESSED(); // Pressed
                if (freeCount > 0)
                {
                    static uint8_t slot;

                    slot = freeQueue[freeHead];
                    if (++freeHead >= MAX_MISSILE)
                        freeHead = 0;
                    freeCount--;
#ifdef TARGET_GG
                    missiles[slot].spawnX = spriteX + 8;
                    missiles[slot].capturedScrollX = scrollX;
                    missiles[slot].capturedScrollY = scrollY;
#endif
                    missiles[slot].x = spriteX + 8;
                    missiles[slot].y = (spriteY + 7) - 1; // SpriteTableY stores y-1
                }
            }
            else
                SET_FIRE_COLOR_RELEASED(); // Released
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

        for (i = 0; i < MAX_MISSILE; i++)
        {
            if (missiles[i].y != 0xe0)
            {
                missiles[i].y -= MISSILE_SPEED;
#ifdef TARGET_GG
                missiles[i].x = missiles[i].spawnX + (scrollX - missiles[i].capturedScrollX);
                // Y scroll delta is applied incrementally each frame since the missile also moves autonomously.
                // Subtract: when viewport scrolls down (scrollY increases), world objects move up on screen.
                missiles[i].y -= scrollY - missiles[i].capturedScrollY;
                missiles[i].capturedScrollY = scrollY;
#endif
                if (missiles[i].y > 0xe0 && missiles[i].y < 0xf0)
                {
                    missiles[i].y = 0xe0;
                    freeQueue[freeTail] = i;
                    if (++freeTail >= MAX_MISSILE)
                        freeTail = 0;
                    freeCount++;
                }
            }
            SMS_updateMetaSpritePosition(missiles[i].spriteID, missiles[i].x, missiles[i].y, missileMetaSprite);
        }
    }
}
