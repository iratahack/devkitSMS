CC = sdcc

ifeq ($(CC),zcc)
AR=z88dk-z80asm
else
AR=sdar
endif


########### BUILD CONFIGURATION ##############

# Enables a faster version of SMS_addSprite (and SMS_add*AdjoiningSprites)
# which does not return a handle and does not check for sprite terminator
# and sprite availability
#CONFIG+=-DNO_SPRITE_CHECKS

# Enables a faster version of SMS_add*AdjoiningSprites through disabling
# support for zoomed sprites
#CONFIG+=-DNO_SPRITE_ZOOM

# Enable support for Megadrive controllers
#CONFIG+=-DMD_PAD_SUPPORT

# Enable support for VDP type detection
#CONFIG+=-DVDPTYPE_DETECTION

# Build a lib supporting less sprites to save memory. Max is 64 (all).
#CONFIG+=-DMAXSPRITES=64

# Omit support for a frame interrupt hook to save a few bytes
# and cycles.
#CONFIG+=-DNO_FRAME_INT_HOOK

############# END OF BUILD CONFIG OPTIONS #############

# Files that are compiled once and used for SMS and GG
SRCS=SMSlib_aPLib.c SMSlib_deprecated.c SMSlib_load1bppTiles.c SMSlib_load2bppTiles.c SMSlib_loadTileMapArea.c SMSlib_loadTileMapColumn.c SMSlib_paddle.c SMSlib_paletteAdd.c SMSlib_paletteSub.c SMSlib_STC0comp.c SMSlib_STC4comp.c SMSlib_PSGaiden.c SMSlib_spriteAdv.c SMSlib_sprite.c SMSlib_STMcomp.c SMSlib_textrenderer.c SMSlib_twosprites.c SMSlib_threesprites.c SMSlib_foursprites.c SMSlib_metasprite.c SMSlib_UNSAFE.c SMSlib_UNSAFE_SAT.c SMSlib_UNSAFE_memcpy.c SMSlib_UNSAFE_aPLib.c SMSlib_VRAMmemcpy_brief.c SMSlib_VRAMmemcpy.c SMSlib_VRAMmemset.c SMSlib_zx7.c SMSlib_zx7_VRAM.c SMSlib_string.c SMSlib_getTile.c SMSlib_readVRAM.c SMSlib_debug.c

ifeq ($(CC),zcc)
OPT=--max-allocs-per-node100000 -SO3 -O3
CFLAGS=+sms -compiler=sdcc --no-nop-comment $(OPT) $(CONFIG)
PEEP_OPTIONS=-custom-copt-rules=rules.copt
ARFLAGS=-x
OBJ_EXT=c.o
else
OPT=--max-allocs-per-node 100000
CFLAGS=-mz80 $(OPT) $(CONFIG)
PEEP_OPTIONS=--peep-file peep-rules.txt
ARFLAGS=r 
OBJ_EXT=rel
endif

OUTPUT_LIBS=SMSlib.lib SMSlib_GG.lib

# One object per common source file. Add target specific object dependencies here.
COMMON_OBJS=$(patsubst %.c,%.$(OBJ_EXT),$(SRCS))
SMS_SPECIFIC_OBJS=$(patsubst %.c,%.$(OBJ_EXT),SMSlib.c SMSlib_autotext.c SMSlib_spriteClip.c SMSlib_paletteZero.c SMSlib_paletteAdv.c)
GG_SPECIFIC_OBJS=$(patsubst %.c,%_GG.$(OBJ_EXT),SMSlib.c SMSlib_autotext.c SMSlib_spriteClip.c SMSlib_paletteZero.c SMSlib_paletteAdv.c)

OBJS_SMS=$(COMMON_OBJS) $(SMS_SPECIFIC_OBJS)
OBJS_GG=$(COMMON_OBJS) $(GG_SPECIFIC_OBJS)

ALL: $(OUTPUT_LIBS)

# Library outputs
SMSlib.lib: $(OBJS_SMS)
	$(AR) $(ARFLAGS)$@ $^

SMSlib_GG.lib: $(OBJS_GG)
	$(AR) $(ARFLAGS)$@ $^


# Specific rules for some files with particular compilation options or specific
# to a target.

# The following are compiled without --peep-rules
SMSlib_zx7.$(OBJ_EXT): SMSlib_zx7.c
	$(CC) $(CFLAGS) -c -o $@ $<

SMSlib_UNSAFE_zx7.$(OBJ_EXT): SMSlib_UNSAFE_zx7.c
	$(CC) $(CFLAGS) -c -o $@ $<

SMSlib_aPLib.$(OBJ_EXT): SMSlib_aPLib.c
	$(CC) $(CFLAGS) -c -o $@ $<

SMSlib_paddle.$(OBJ_EXT): SMSlib_paddle.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Default rules
%.$(OBJ_EXT): %.c SMSlib.h peep-rules.txt
	$(CC) $(CFLAGS) $(PEEP_OPTIONS) -c -o $@ $<

# GG rules
%_GG.$(OBJ_EXT): %.c SMSlib.h peep-rules.txt
	$(CC) $(CFLAGS) $(PEEP_OPTIONS) -c -o $@ $< -DTARGET_GG

clean:
	rm -f $(OUTPUT_LIBS) $(OBJS_SMS) $(OBJS_GG) *.lst *.sym *.asm
