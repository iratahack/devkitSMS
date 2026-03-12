CC=zcc
LD=zcc

DEVKITSMS_BASE=../..
SMSLIB_BASE=$(DEVKITSMS_BASE)/SMSlib
SMSLIB_INCDIR=$(SMSLIB_BASE)/src
SMSLIB_LIB=$(SMSLIB_BASE)/zSMSlib.lib

CONFIG=-DVDPTYPE_DETECTION
TARGET=+sms
CFLAGS=$(TARGET) $(CONFIG) -compiler=sdcc -I$(SMSLIB_INCDIR) -c
LDFLAGS=$(TARGET) $(CONFIG) -pragma-redirect:fputc_cons=_SMS_putchar -m -l$(SMSLIB_LIB) -create-app

PROGNAME=hello
SRCS=$(wildcard *.c)
OBJS=$(patsubst %.c,%.o,$(SRCS))

.PHONY: all dis clean distclean

all: $(SMSLIB_LIB) $(PROGNAME).sms

dis: all
	z88dk-dis -x $(PROGNAME).map $(PROGNAME).sms | less

%.o: %.c
	$(CC) $(CFLAGS) -o $@ $<

%.sms: $(OBJS)
	$(LD) $(LDFLAGS) -o $@ $^

$(SMSLIB_LIB):
	@echo "Building SMSlib for z88dk"
	@make -C $(SMSLIB_INCDIR) CC=zcc CONFIG+=$(CONFIG)
	@cp $(SMSLIB_INCDIR)/SMSlib.lib $(SMSLIB_BASE)/zSMSlib.lib
	@cp $(SMSLIB_INCDIR)/SMSlib_GG.lib $(SMSLIB_BASE)/zSMSlib_GG.lib

clean:
	rm -f *.o *.bin *.sms *.map

distclean: clean
	@make -C $(SMSLIB_INCDIR) CC=zcc clean
	@rm -f $(SMSLIB_BASE)/zSMSlib_GG.lib $(SMSLIB_BASE)/zSMSlib.lib
