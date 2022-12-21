#!/usr/bin/env python3

# Copyright (C) 2011-2016 WikiTeam
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Instructions: https://github.com/WikiTeam/wikiteam/wiki/Tutorial#Download_a_list_of_wikis

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .dumpgenerator.domain import domain2prefix

def main():
    PATH_7Z = "7z"

    if len(sys.argv) < 2:
        print("python script.py file-with-apis.txt")
        sys.exit()

    print("Reading list of APIs from", sys.argv[1])
    wikis = open(sys.argv[1]).read().splitlines()
    print("%d APIs found" % (len(wikis)))

    for wiki in wikis:
        print("#" * 73)
        print("# Downloading", wiki)
        print("#" * 73)
        wiki = wiki.lower()
        # Make the prefix in standard way; api and index must be defined, not important which is which
        prefix = domain2prefix(config={"api": wiki, "index": wiki})

        # check if compressed, in that case dump was finished previously
        compressed = False
        for f in os.listdir("."):
            if f.endswith(".7z") and f.split("-")[0] == prefix:
                compressed = True
                zipfilename = f
                break  # stop searching, dot not explore subdirectories

        if compressed:
            print(
                "Skipping... This wiki was downloaded and compressed before in",
                zipfilename,
            )
            # Get the archive's file list.
            if (sys.version_info[0] == 3) and (sys.version_info[1] > 0):
                archivecontent = subprocess.check_output([PATH_7Z, "l", zipfilename, "-scsUTF-8"], text=True, encoding = "UTF-8", errors="strict")
                if re.search(r"%s.+-history\.xml" % (prefix), archivecontent) is None:
                    # We should perhaps not create an archive in this case, but we continue anyway.
                    print("ERROR: The archive contains no history!")
                if re.search(r"Special:Version\.html", archivecontent) is None:
                    print(
                        "WARNING: The archive doesn't contain Special:Version.html, this may indicate that download didn't finish."
                    )
            else:
                print(
                    "WARNING: Content of the archive not checked, we need 3.1+."
                )
                # TODO: Find a way like grep -q below without doing a 7z l multiple times?
            continue

        # download
        started = False  # was this wiki download started before? then resume
        wikidir = ""
        for f in os.listdir("."):
            # Does not find numbered wikidumps not verify directories
            if f.endswith("wikidump") and f.split("-")[0] == prefix:
                wikidir = f
                started = True
                break  # stop searching, dot not explore subdirectories

        # time.sleep(60)
        # Uncomment what above and add --delay=60 in the py calls below for broken wiki farms
        # such as editthis.info, wiki-site.com, wikkii (adjust the value as needed;
        # typically they don't provide any crawl-delay value in their robots.txt).
        if started and wikidir:  # then resume
            print("Resuming download, using directory", wikidir)
            subprocess.call(
                [
                    sys.executable,
                    "-c",
                    "import wikiteam3.dumpgenerator; wikiteam3.dumpgenerator.main()",
                    f"--api={wiki}",
                    "--xml",
                    "--images",
                    "--resume",
                    f"--path={wikidir}",
                ],
                shell=False,
            )
        else:  # download from scratch
            subprocess.call(
                [
                    sys.executable,
                    "-c",
                    "import wikiteam3.dumpgenerator; wikiteam3.dumpgenerator.main()",
                    f"--api={wiki}",
                    "--xml",
                    "--images",
                ],
                shell=False,
            )
            started = True
            # save wikidir now
            for f in os.listdir("."):
                # Does not find numbered wikidumps not verify directories
                if f.endswith("wikidump") and f.split("-")[0] == prefix:
                    wikidir = f
                    break  # stop searching, dot not explore subdirectories

        prefix = wikidir.split("-wikidump")[0]

        finished = False
        if started and wikidir and prefix:
            if subprocess.call(
                [
                    'tail -n 1 %s/%s-history.xml | grep -q "</mediawiki>"'
                    % (wikidir, prefix)
                ],
                shell=True,
            ):
                print(
                    "No </mediawiki> tag found: dump failed, needs fixing; resume didn't work. Exiting."
                )
            else:
                finished = True
        # You can also issue this on your working directory to find all incomplete dumps:
        # tail -n 1 */*-history.xml | grep -Ev -B 1 "</page>|</mediawiki>|==|^$"

        # compress
        if finished:
            time.sleep(1)
            os.chdir(wikidir)
            print("Changed directory to", os.getcwd())
            # Basic integrity check for the xml. The script doesn't actually do anything, so you should check if it's broken. Nothing can be done anyway, but redownloading.
            subprocess.call(
                'grep "<title>" *.xml -c;grep "<page>" *.xml -c;grep "</page>" *.xml -c;grep "<revision>" *.xml -c;grep "</revision>" *.xml -c',
                shell=True,
            )

            pathHistoryTmp = Path("..", prefix + "-history.xml.7z.tmp")
            pathHistoryFinal = Path("..", prefix + "-history.xml.7z")
            pathFullTmp = Path("..", prefix + "-wikidump.xml.7z.tmp")
            pathFullFinal = Path("..", prefix + "-wikidump.xml.7z")

            # Make a non-solid archive with all the text and metadata at default compression. You can also add config.txt if you don't care about your computer and user names being published or you don't use full paths so that they're not stored in it.
            compressed = subprocess.call(
                [
                    PATH_7Z,
                    "a",
                    "-ms=off",
                    "--",
                    str(pathHistoryTmp),
                    f"{prefix}-history.xml",
                    f"{prefix}-titles.txt",
                    "index.html",
                    "Special:Version.html",
                    "errors.log",
                    "siteinfo.json",
                ],
                shell=False,
            )
            if compressed < 2:
                pathHistoryTmp.rename(pathHistoryFinal)
            else:
                print("ERROR: Compression failed, will have to retry next time")
                pathHistoryTmp.unlink()

            # Now we add the images, if there are some, to create another archive, without recompressing everything, at the min compression rate, higher doesn't compress images much more.
            shutil.copy(pathHistoryFinal, pathFullTmp)

            subprocess.call(
                [
                    PATH_7Z,
                    "a",
                    "-ms=off",
                    "-mx=1",
                    "--",
                    str(pathFullTmp),
                    f"{prefix}-images.txt",
                    "images/",
                ],
                shell=False,
            )

            pathFullTmp.rename(pathFullFinal)

            os.chdir("..")
            print("Changed directory to", os.getcwd())
            time.sleep(1)


if __name__ == "__main__":
    main()
