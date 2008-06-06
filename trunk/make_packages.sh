#!/bin/bash
#############################################################
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
ln -s ../pys60gps.py default.py
ln -s ../plugins plugins
for py in ../lib/*.py;
  do ln -s $py .
done


