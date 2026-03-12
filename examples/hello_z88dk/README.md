# SMSlib example for z88dk

For platform(s): SMS

## Purpose

Show how to:
 - Compile and link code with SMSlib and z88dk
 - Initialize the SMSlib subsystem (`SMS_init`, `SMS_useFirstHalfTilesforSprites`, `SMS_autoSetUpTextRenderer`, `SMS_loadBGPalette`, `SMS_loadSpritePalette`)
 - Link z88dk interrupts to SMSlib ISRs (`add_raster_int(SMS_isr)`, `add_pause_int(SMS_nmi_isr)`)
 - Display text using `printf`, `SMS_print`, and `SMS_printatXY` (positioned with `SMS_setNextTileatXY`)
 - Set up and move a double-wide sprite (two adjoining sprites) with the D-pad (`SMS_addTwoAdjoiningSprites`, `SMS_updateSpritePosition`, `SMS_copySpritestoSAT`)
 - Change sprite palette colour on button 1 and button 2 press/release (`SMS_getKeysStatus`, `SMS_setSpritePaletteColor`)
 - Pause and unpause the game (Pause button), saving and restoring the tilemap (`SMS_queryPauseRequested`, `SMS_resetPauseRequest`, `SMS_saveTileMapArea`, `SMS_loadTileMapArea`)
 - Soft-reset on the Reset button (`SMS_displayOff`, `SMS_zeroSpritePalette`, `SMS_zeroBGPalette`)

## Screenshots

Initial screen (before any controller input):

![Expected result](screenshots/hello.png)

## Compilation

The included Makefile will build the library before building the application.

It is assumed that z88dk is in your path.

### Make targets

| Target | Description |
|--------|-------------|
| `make` / `make all` | Build SMSlib (if needed) then compile and link `hello.sms` |
| `make dis` | Disassemble `hello.sms` using `z88dk-dis` and the generated map file (requires `z88dk-dis` in path) |
| `make clean` | Remove local build artifacts (`*.o`, `*.bin`, `*.sms`, `*.map`) |
| `make distclean` | Like `clean`, but also removes the built SMSlib library and its object files |
