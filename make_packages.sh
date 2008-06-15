#!/bin/bash
#############################################################
# $Id$
# Copyright Aapo Rista 2008
# Create a few different packages which can be used to
# install pys60gps to a s60-phone.
#############################################################

# Cleanup old stuff

rm -f pys60gps.zip
rm -Rf sis

# Create a zip-package.
# Installation:
# 1. transfer it to the phone
# 2. extract it into E:\Python with phone's ZipManager

find pys60gps.py lib  -name "*.py" | zip -@ pys60gps.zip

# Create a directory hierarchy for SIS-package

mkdir sis
pushd sis
cp -p ../pys60gps.py default.py
echo "appuifw.app.set_exit()" >> default.py
cp -rp ../plugins plugins
for py in ../lib/*.py;
  do cp -p $py .
done
popd

# Check if ensyble is found in path
# and created unsigned (selfsigned?) sis package

ENSYMBLE=$(which ensymble)
if [ -z ${ENSYMBLE} ];
then
  echo Did not found ensymble from the path.
  echo Download ensymble from here:
  echo http://www.nbl.fi/~nbl928/ensymble.html
  echo and put it somewhere into your PATH e.g. ~/bin/.
  exit 1;
fi;

# TODO: 
${ENSYMBLE} py2sis sis pys60gps.sis

