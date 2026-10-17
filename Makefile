PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=
VERSION := $(shell PYTHONPATH=. $(PYTHON) -c "import bytekeys; print(bytekeys.__version__)")

.PHONY: help run demo cli test check deb appimage install uninstall clean

help:
	@echo "ByteKeys $(VERSION)"
	@echo "  make run        open the control panel from the source tree"
	@echo "  make demo       control panel with simulated keyboards (no service)"
	@echo "  make test       run the test suite"
	@echo "  make check      byte-compile and test"
	@echo "  make deb        build dist/bytekeys_$(VERSION)_all.deb"
	@echo "  make appimage   build dist/ByteKeys-$(VERSION)-$$(uname -m).AppImage"
	@echo "  make install    install to $(PREFIX) and enable the service (needs root)"
	@echo "  make uninstall  remove a 'make install' installation (needs root)"

run:
	$(PYTHON) -m bytekeys gui

demo:
	$(PYTHON) -m bytekeys gui --demo --local

cli:
	$(PYTHON) -m bytekeys status

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

check:
	$(PYTHON) -m compileall -q bytekeys tests
	$(PYTHON) -m unittest discover -s tests -t .

deb:
	packaging/deb/build-deb.sh

appimage:
	packaging/appimage/build-appimage.sh

install:
	packaging/stage.sh "$(DESTDIR)" "$(PREFIX)" /etc/systemd/system
	@if [ -z "$(DESTDIR)" ] && [ -d /run/systemd/system ]; then \
		systemctl daemon-reload && systemctl enable --now bytekeysd.service; \
	fi

uninstall:
	-systemctl disable --now bytekeysd.service
	rm -rf "$(DESTDIR)$(PREFIX)/lib/bytekeys"
	rm -f "$(DESTDIR)$(PREFIX)/bin/bytekeys" "$(DESTDIR)$(PREFIX)/bin/bytekeys-gui" "$(DESTDIR)$(PREFIX)/sbin/bytekeysd"
	rm -f "$(DESTDIR)/etc/systemd/system/bytekeysd.service"
	rm -f "$(DESTDIR)$(PREFIX)/share/applications/io.github.bytekeys.ByteKeys.desktop"
	rm -f "$(DESTDIR)$(PREFIX)/share/metainfo/io.github.bytekeys.ByteKeys.metainfo.xml"
	rm -f "$(DESTDIR)$(PREFIX)/share/man/man1/bytekeys.1.gz" "$(DESTDIR)$(PREFIX)/share/man/man1/bytekeys-gui.1.gz" \
		"$(DESTDIR)$(PREFIX)/share/man/man8/bytekeysd.8.gz"
	find "$(DESTDIR)$(PREFIX)/share/icons/hicolor" -name 'io.github.bytekeys.ByteKeys.*' -delete
	-systemctl daemon-reload

clean:
	rm -rf build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
