CC=zcc
LD=zcc

DEVKITSMS_BASE=../..
SMSLIB_BASE=$(DEVKITSMS_BASE)/SMSlib
SMSLIB_INCDIR=$(SMSLIB_BASE)/src

# Set GG=1 to build for Game Gear (e.g. make GG=1)
GG ?= 0

TARGET=+sms

ifeq ($(GG),1)
CONFIG=-DTARGET_GG
SUBTYPE=-subtype=gamegear
SMSLIB_LIB=$(SMSLIB_BASE)/zSMSlib_GG.lib
ROM_EXT=gg
else
CONFIG=-DVDPTYPE_DETECTION
SUBTYPE=
SMSLIB_LIB=$(SMSLIB_BASE)/zSMSlib.lib
ROM_EXT=sms
endif

CFLAGS=$(TARGET) $(SUBTYPE) $(CONFIG) -compiler=sdcc -I$(SMSLIB_INCDIR) -c
LDFLAGS=$(TARGET) $(SUBTYPE) $(CONFIG) -pragma-redirect:fputc_cons=_SMS_putchar -m -l$(SMSLIB_LIB) -create-app

PROGNAME=hello
SRCS=$(wildcard *.c)
OBJS=$(patsubst %.c,%.o,$(SRCS))
ROM=$(PROGNAME).$(ROM_EXT)

.PHONY: all dis clean distclean

all: $(SMSLIB_LIB) $(ROM)

dis: all
	z88dk-dis -x $(PROGNAME).map $(ROM) | less

%.o: %.c
	$(CC) $(CFLAGS) -o $@ $<

$(ROM): $(OBJS)
	$(LD) $(LDFLAGS) -o $@ $^

$(SMSLIB_LIB):
	@echo "Building SMSlib for z88dk"
	@make -C $(SMSLIB_INCDIR) CC=zcc CONFIG+=$(CONFIG)
	@cp $(SMSLIB_INCDIR)/SMSlib.lib $(SMSLIB_BASE)/zSMSlib.lib
	@cp $(SMSLIB_INCDIR)/SMSlib_GG.lib $(SMSLIB_BASE)/zSMSlib_GG.lib

clean:
	rm -f *.o *.bin *.sms *.gg *.map

distclean: clean
	@make -C $(SMSLIB_INCDIR) CC=zcc clean
	@rm -f $(SMSLIB_BASE)/zSMSlib_GG.lib $(SMSLIB_BASE)/zSMSlib.lib
