.PHONY: all clean
all: zh_CN-kawaii

build:
	mkdir -p build

%: src/%.po | build
	msgfmt -o build/$*.mo $<

clean:
	rm -rf build
