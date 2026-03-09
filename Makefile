# ============================================================
#  Advanced Bookmarks — developer Makefile
# ============================================================

EXTENSION_NAME := advanced-bookmarks
BUILD_DIR      := build
ZIP_FILE       := $(BUILD_DIR)/$(EXTENSION_NAME).zip

# Files/dirs to exclude from the distribution zip
ZIP_EXCLUDES := \
	"*.git*"          \
	"$(BUILD_DIR)/*"  \
	"scripts/*"       \
	"*.md"            \
	"Makefile"        \
	".DS_Store"       \
	"*.crx"           \
	"*.pem"           \
	".claude/*"

.DEFAULT_GOAL := help

# ────────────────────────────────────────
.PHONY: help
help:                ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ────────────────────────────────────────
.PHONY: icons
icons:               ## Regenerate PNG icons (requires Python 3)
	@echo "Generating icons..."
	python3 scripts/generate-icons.py
	@echo "Done."

# ────────────────────────────────────────
.PHONY: validate
validate:            ## Validate manifest.json and check all referenced files exist
	python3 scripts/validate.py

# ────────────────────────────────────────
.PHONY: pack
pack: icons validate ## Build a .zip ready for Chrome Web Store upload
	@echo "Packaging extension..."
	@mkdir -p $(BUILD_DIR)
	@rm -f $(ZIP_FILE)
	@zip -r $(ZIP_FILE) . $(addprefix --exclude , $(ZIP_EXCLUDES)) > /dev/null
	@echo "Created $(ZIP_FILE)"
	@echo "Size: $$(du -sh $(ZIP_FILE) | cut -f1)"
	@echo ""
	@echo "Contents:"
	@unzip -l $(ZIP_FILE) | tail -n +4 | head -n -2 | awk '{print "  " $$4}'

# ────────────────────────────────────────
.PHONY: sign
sign:                ## Pack and self-sign a .crx (for local/enterprise use — NOT for Web Store)
	@if [ -z "$(CHROME)" ]; then \
		CHROME_BIN=$$(ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null || \
		              ls "/Applications/Chromium.app/Contents/MacOS/Chromium" 2>/dev/null || \
		              which google-chrome 2>/dev/null || \
		              which chromium 2>/dev/null); \
	else \
		CHROME_BIN="$(CHROME)"; \
	fi; \
	if [ -z "$$CHROME_BIN" ]; then \
		echo "Could not find Chrome. Set CHROME=/path/to/chrome and retry."; exit 1; \
	fi; \
	mkdir -p $(BUILD_DIR); \
	ABS_EXT=$$(pwd); \
	KEY_FILE=$(BUILD_DIR)/$(EXTENSION_NAME).pem; \
	if [ -f "$$KEY_FILE" ]; then \
		echo "Using existing key: $$KEY_FILE"; \
		"$$CHROME_BIN" --pack-extension="$$ABS_EXT" --pack-extension-key="$$KEY_FILE" 2>/dev/null; \
	else \
		echo "No key found — Chrome will generate one."; \
		"$$CHROME_BIN" --pack-extension="$$ABS_EXT" 2>/dev/null; \
		mv "$$(dirname $$ABS_EXT)/$$(basename $$ABS_EXT).crx" $(BUILD_DIR)/$(EXTENSION_NAME).crx 2>/dev/null || true; \
		mv "$$(dirname $$ABS_EXT)/$$(basename $$ABS_EXT).pem" $$KEY_FILE 2>/dev/null || true; \
		echo "IMPORTANT: Keep $$KEY_FILE safe — it is your extension's permanent identity."; \
	fi; \
	ls -lh $(BUILD_DIR)/*.crx 2>/dev/null || echo "Note: .crx may have been written next to the extension folder."

# ────────────────────────────────────────
.PHONY: resize-screenshots
resize-screenshots:  ## Resize screenshots to 1280x800 (keeps ratio, pads with white). Requires ImageMagick.
	@bash scripts/resize-screenshots.sh

# ────────────────────────────────────────
.PHONY: clean
clean:               ## Remove build artifacts
	rm -rf $(BUILD_DIR)
	@echo "Cleaned."

# ────────────────────────────────────────
.PHONY: dev
dev:                 ## Open chrome://extensions in Chrome (then click Reload or Load unpacked)
	@CHROME=$$(ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null || \
	            which google-chrome 2>/dev/null || \
	            which chromium 2>/dev/null); \
	if [ -n "$$CHROME" ]; then \
		open -a "Google Chrome" "chrome://extensions" 2>/dev/null || \
		"$$CHROME" "chrome://extensions"; \
	else \
		echo "Chrome not found. Open chrome://extensions manually."; \
	fi

# ────────────────────────────────────────
.PHONY: shortcuts
shortcuts:           ## Open chrome://extensions/shortcuts to configure the keyboard shortcut
	@open -a "Google Chrome" "chrome://extensions/shortcuts" 2>/dev/null || \
	 google-chrome "chrome://extensions/shortcuts" 2>/dev/null || \
	 echo "Open chrome://extensions/shortcuts in Chrome to configure your shortcut."
