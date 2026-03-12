# SMSlib example for z88dk

For platform(s): SMS, Game Gear

## Purpose

Show how to:
 - Compile and link code with SMSlib and z88dk for both SMS and Game Gear
 - Initialize the SMSlib subsystem (`SMS_init`, `SMS_useFirstHalfTilesforSprites`, `SMS_autoSetUpTextRenderer`, `SMS_loadBGPalette`/`GG_loadBGPalette`, `SMS_loadSpritePalette`/`GG_loadSpritePalette`)
 - Link z88dk interrupts to SMSlib ISRs (`add_raster_int(SMS_isr)`, `add_pause_int(SMS_nmi_isr)` — SMS only)
 - Display text using `printf`, `SMS_print`, and `SMS_printatXY` (positioned with `SMS_setNextTileatXY`), accounting for the GG viewport offset
 - Set up and move a double-wide sprite (two adjoining sprites) with the D-pad (`SMS_addTwoAdjoiningSprites`, `SMS_updateSpritePosition`, `SMS_copySpritestoSAT`), clamped to the visible screen area
 - Change sprite palette colour on button 1 and button 2 press/release (`SMS_getKeysStatus`, `SMS_setSpritePaletteColor`/`GG_setSpritePaletteColor`)
 - Pause and unpause the game (Pause button — SMS only), saving and restoring the tilemap (`SMS_queryPauseRequested`, `SMS_resetPauseRequest`, `SMS_saveTileMapArea`, `SMS_loadTileMapArea`)
 - Soft-reset on the Reset button — SMS only (`SMS_displayOff`, `SMS_zeroSpritePalette`, `SMS_zeroBGPalette`)

## Screenshots

Initial screen (before any controller input):

![Expected result](screenshots/hello.png)

## Compilation

The included Makefile will build the library before building the application.

It is assumed that z88dk is in your path.

### Building for SMS (default)

```sh
make
```

Produces `hello.sms`.

### Building for Game Gear

```sh
make GG=1
```

Produces `hello.gg`. This passes `-subtype=gamegear` and `-DTARGET_GG` to z88dk, selects
`zSMSlib_GG.lib`, and adjusts screen dimensions and the viewport tile/pixel offsets in the
source for the GG's 160×144 visible window.

### Make targets

| Target | Description |
|--------|-------------|
| `make` / `make all` | Build `zSMSlib.lib` (if needed) then compile and link `hello.sms` |
| `make GG=1` | Build `zSMSlib_GG.lib` (if needed) then compile and link `hello.gg` for Game Gear |
| `make dis` | Disassemble the ROM using `z88dk-dis` and the generated map file (requires `z88dk-dis` in path) |
| `make clean` | Remove local build artifacts (`*.o`, `*.bin`, `*.sms`, `*.gg`, `*.map`) |
| `make distclean` | Like `clean`, but also removes the built SMSlib libraries and their object files |
