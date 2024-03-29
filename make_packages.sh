#!/bin/bash
#############################################################
# $Id$
# Copyright Aapo Rista 2008-2009
# Create a few different packages which can be used to
# install pys60gps to a s60-phone.
#############################################################

# Find out version string

SIS_VERSION=$(perl -ne 'if (/SIS_VERSION\s*=\s*"([\d\.]+)"/) {print "-$1";}' pys60gps.py)
# REVISION=$(perl -ne 'if (/\$Id: pys60gps.py (\d+)/) {print "-rev$1";exit()}' pys60gps.py)
svn up
REVISION=-rev$(svn info|grep Revision:|cut -d' ' -f2) # Revision: 156

APP="plokin"
SHORTCAPTION="Plok.in"
CAPTION="Plok.in mobile"


# Cleanup old stuff

rm -f pys60gps*.zip
rm -Rf sis
rm -Rf *.sis

# Create a zip-package.
# Installation:
# 1. transfer it to the phone
# 2. extract it into E:\Python with phone's ZipManager

find pys60gps.py lib  -name "*.py" | zip -@ pys60gps${SIS_VERSION}${REVISION}.zip

# Create a directory hierarchy for SIS-package

mkdir sis
pushd sis
cp -p ../pys60gps.py default.py
echo "appuifw.app.set_exit()" >> default.py
mkdir -p plugins
cp -p ../plugins/*.py plugins/
for py in ../lib/*.py;
  do cp -p $py .
done
popd

# Check if ensyble is found in path
# and create selfsigned sis package

ENSYMBLE=$(which ensymble)
echo ${ENSYMBLE}
if [ -z ${ENSYMBLE} ];
then
  echo Did not found ensymble from the path.
  echo Download ensymble from here:
  echo http://code.google.com/p/ensymble/
  echo and put it somewhere into your PATH e.g. ~/bin/.
  exit 1;
fi;

# http://www.forum.nokia.com/main/platforms/s60/capability_descriptions.html
# Create unsigned testrange package
python2.5 ${ENSYMBLE} py2sis --heapsize=4k,5M --uid=0xE00184F0 --appname=Pys60Gps --lang=EN --textfile=CHANGELOG.txt --shortcaption="Pys60Gps" --caption="PyS60 GPS (opennetmap.org)"  --drive=C --caps=ALL-TCB-DRM-AllFiles-CommDD-MultimediaDD-NetworkControl-DiskAdmin --vendor="Plokaus Oy" --runinstall --verbose sis pys60gps${SIS_VERSION}_unsigned_testrange.sis

if [ -z $1 ];
then
  echo NOTE: If you want to create signed version,
  echo give the file body of your cers as an argument.
  echo sh $0 mycert # you must have mycert.cer and mycert.key
  exit 0
fi

# Create signed version
python2.5 ${ENSYMBLE} py2sis --heapsize=4k,5M --uid=0x200184F0 --appname=Pys60Gps  --icon="${APP}.svg" --lang=EN --textfile=CHANGELOG.txt --shortcaption="Pys60Gps" --caption="PyS60 GPS (opennetmap.org)"  --drive=C --caps=ALL-TCB-DRM-AllFiles --vendor="Plokaus Oy" --runinstall --verbose --cert=$1.cer  --privkey=$1.key sis $1-pys60gps${SIS_VERSION}-signed.sis

# Create selfsigned version
#python2.5 ${ENSYMBLE} py2sis --appname=${APP} --icon="${APP}.svg" --lang=EN --textfile=CHANGELOG.txt --shortcaption="${SHORTCAPTION}" --caption="${CAPTION}" --drive=C --caps=LocalServices+UserEnvironment+NetworkServices+ReadUserData+WriteUserData --vendor="TaiK MediaLab Arki" --runinstall --verbose sis ${APP}${SIS_VERSION}-selfsigned.sis
python2.5 ${ENSYMBLE} py2sis --appname=${APP} --icon="${APP}.svg" --lang=EN --textfile=CHANGELOG.txt --shortcaption="${SHORTCAPTION}" --caption="${CAPTION}" --drive=C --caps=Location+LocalServices+UserEnvironment+NetworkServices+ReadUserData+WriteUserData --vendor="Plokaus" --runinstall --verbose sis ${APP}${SIS_VERSION}-selfsigned.sis
