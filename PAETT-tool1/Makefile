all:
	mkdir -p bin
	mkdir -p lib
	cd src; make; cd ..
	cd apps; make; cd ..
	cd tools; make; cd ..
	cd scripts; make; cd ..

clean:
	cd src; make clean; cd ..
	cd apps; make clean; cd ..
	cd tools; make clean; cd ..

very-clean: clean
	rm -rf bin lib