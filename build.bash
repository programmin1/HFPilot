# build deploy directory:
/mingw64/bin/pyinstaller -i "resources/hfpilot.ico" ./hfpilot.spec
echo "Cleaning up."
rm -rf dist/hfpilot/share/locale
rm -rf dist/hfpilot/share/icons/hicolor
rm -rf dist/hfpilot/share/icons/Adwaita/512x512
rm -rf dist/hfpilot/share/icons/Adwaita/256x256
rm -rf dist/hfpilot/share/icons/Adwaita/96x96
rm -rf dist/hfpilot/share/icons/Adwaita/64x64
rm -rf dist/hfpilot/share/icons/Adwaita/48x48
rm -rf dist/hfpilot/share/icons/Adwaita/32x32
rm -rf dist/hfpilot/share/icons/Adwaita/22x22/devices
rm -rf dist/hfpilot/share/icons/Adwaita/22x22/places
rm -rf dist/hfpilot/share/icons/Adwaita/22x22/status
rm -rf dist/hfpilot/share/icons/Adwaita/22x22/emblems


rm -rf dist/hfpilot/share/icons/Adwaita/16x16/devices
rm -rf dist/hfpilot/share/icons/Adwaita/16x16/places
rm -rf dist/hfpilot/share/icons/Adwaita/16x16/status
rm -rf dist/hfpilot/share/icons/Adwaita/16x16/emblems
rm -rf dist/hfpilot/share/icons/Adwaita/16x16/emotes



echo "Cleaned - now run NSIS"