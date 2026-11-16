# Build every task of this lab against the study kernel: run make here.
# Kbuild in this directory lists the tasks; make lab also stages them.
KDIR ?= $(CURDIR)/../../linux-5.15.2
KCC ?= gcc-11

all:
	$(MAKE) -C $(KDIR) ARCH=x86 CC=$(KCC) HOSTCC=$(KCC) M=$(CURDIR) modules

clean:
	$(MAKE) -C $(KDIR) ARCH=x86 CC=$(KCC) HOSTCC=$(KCC) M=$(CURDIR) clean

.PHONY: all clean
