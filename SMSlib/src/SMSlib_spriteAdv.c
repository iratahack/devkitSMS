/* **************************************************
   SMSlib - C programming library for the SMS/GG
   ( part of devkitSMS - github.com/sverx/devkitSMS )
   ************************************************** */

#include "SMSlib.h"
#include "SMSlib_common.c"

signed char SMS_reserveSprite (void) {
  if (SpriteNextFree<MAXSPRITES) {
    SpriteTableY[SpriteNextFree]=0xE0;            // so it's offscreen
    return(SpriteNextFree++);
  }
  return (-1);
}

void SMS_updateSpritePosition (signed char sprite, unsigned char x, unsigned char y) {
  if (y!=0xD1) {                                  // avoid placing sprites at this Y!
    SpriteTableY[(unsigned char)sprite]=(unsigned char)(y-1);
    SpriteTableXN[(unsigned char)sprite*2]=x;
  } else {
    SpriteTableY[(unsigned char)sprite]=0xE0;     // move it offscreen anyway
  }
}

void SMS_updateSpriteImage (signed char sprite, unsigned char tile) {
  SpriteTableXN[(unsigned char)sprite*2+1]=tile;
}

void SMS_hideSprite (signed char sprite) {
  SpriteTableY[(unsigned char)sprite]=0xE0;          // move it offscreen
}

#pragma save
#pragma disable_warning 85
void SMS_updateMetaSpriteImage_f (unsigned char id, const void *tiles) __naked __sdcccall(1) {
  // id    in HL: L = sprite slot index (H = unused)
  // tiles in DE: pointer to tile array terminated by METASPRITE_END
  __asm
    add a
    ld c,a
    ld b,#0
    ld hl,#_SpriteTableXN
    add hl,bc            ; HL = &SpriteTableXN[id*2]
    inc hl               ; HL = &SpriteTableXN[id*2+1]  (tile slot)
    ex de,hl             ; DE = tile slot address, HL = *tiles

update_image_loop:
    ld a,(hl)            ; read next tile from array
    cp #255		 ; This means you cannot use tile ID 255
    ret z

    ld (de),a            ; write tile to SpriteTableXN[sprite*2+1]
    inc hl               ; advance to next entry in tile array
    inc de               ; skip X byte of next sprite
    inc de               ; land on tile byte of next sprite
    jp update_image_loop
  __endasm;
}
#pragma restore

#pragma save
#pragma disable_warning 85
void SMS_updateMetaSpritePosition_f (unsigned int id_y, unsigned int x, const void *metasprite) __naked __z88dk_callee __sdcccall(1) {
  // id_y in HL: H = y_origin, L = id (sprite slot index)
  // x    in DE: E = x_origin (D = unused)
  // metasprite on stack
  __asm
    ; --- Prologue: pack IY with origins, load table pointers ---

    ld c,l               ; C = id
    ld l,e               ; HL: H=y_origin, L=x_origin  (mirroring SMS_addMetaSprite_f convention)
    push hl
    pop iy               ; IYH = y_origin, IYL = x_origin

    pop hl               ; HL = return address
    ex (sp),hl           ; HL = *metasprite, [SP] = return address  (callee-saves ret addr)

    ; Set up DE = &SpriteTableXN[id*2] and BC = &SpriteTableY[id]
    ; SpriteTableXN is computed first so B=0 is still valid; pop bc for SpriteTableY sets
    ; BC to the full RAM address needed by the loop and must be the last thing we touch.
    ld b,#0
    ld a,c               ; A = id  (save — C will be clobbered by sla below)

    push hl              ; save *metasprite

    ld hl,#_SpriteTableXN
    sla c                ; C = id * 2  (B still 0)
    add hl,bc            ; HL = &SpriteTableXN[id*2]
    ex de,hl             ; DE = &SpriteTableXN[id*2]

    ld c,a               ; C = id  (restore; B still 0 — ex de,hl does not touch BC)
    ld hl,#_SpriteTableY
    add hl,bc            ; HL = &SpriteTableY[id]
    push hl
    pop bc               ; BC = &SpriteTableY[id]  — correct full address for the loop

    pop hl               ; HL = *metasprite

    ; --- Main loop ---
update_metasprite_loop:
    ld a,(hl)            ; read delta_x
    cp #METASPRITE_END
    ret z                ; done — [SP] holds the return address

    inc hl
    .db 0xFD
    add a,l              ; add a,iyl  ; final_x = delta_x + x_origin
    ld (de),a            ; write X to SpriteTableXN[sprite*2]

    ld a,(hl)            ; read delta_y
    inc hl
    inc hl               ; skip tile number (not modified by this function)

    .db 0xFD
    add a,h              ; add a,iyh  ; final_y = delta_y + y_origin

    cp #0xD1             ; Y=0xD1 would store 0xD0 = SAT list-terminator; use offscreen instead
    jr z,update_ms_offscreen

    dec a                ; SAT stores Y-1
    ld (bc),a            ; write Y to SpriteTableY[sprite]
    jr update_ms_next

update_ms_offscreen:
    ld a,#0xE0
    ld (bc),a            ; move sprite offscreen

update_ms_next:
    inc bc               ; advance to SpriteTableY[sprite+1]
    inc de               ; skip tile byte in SpriteTableXN
    inc de               ; advance to SpriteTableXN[(sprite+1)*2]
    jp update_metasprite_loop
  __endasm;
}
#pragma restore
