
# vim: noexpandtab tabstop=8 shiftwidth=8


DATES = $(wildcard *.date)
HTML = $(DATES:.date=.html)

%.html: %.date
	python3 startlist-runner.py --crossmgr racedb.wimsey.online --html --date racedb.wg --date $(<:.date=) 


all:
	@echo "make sdist | install | uninstall | bdist"

test:
	@echo $(DATES)
	@echo $(HTML)

test-clean:
	-rm -f *html *xlsx

lists: $(HTML)

clean:
	rm -f */*pyc
	rm -rf build dist *.egg-info

.PHONY: sdist install bdist


bdist:
	python3 setup.py $@
sdist:
	python3 setup.py $@
install:
	python3 setup.py $@
install-support:
	set -x; cp -vr bin/* /usr/local/bin

uninstall:
	pip3 uninstall qlmux

sync:
	aws s3 sync --region us-west-2 . s3://wimseyraceresults/2024/testing --exclude='*' --include='*.html'
