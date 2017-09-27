#!/bin/sh
set -e
echo "\033[1;92m1. Making new version ...\033[0m"
sleep 0.3
bumpversion patch

echo "\033[1;92m2. Pushing to GIT... \033[1;91m(Dont run this script again in case of errors) \033[0m"
git push
git push origin --tags
sleep 0.3

echo "\033[0;92m You have successfully created new version of smartsched.\nNow you should manually upload it to PyPi.\nIf you have no right to do that ask gavelock+smartsched@gmail.com"

#python3 setup.py bdist_wheel upload
