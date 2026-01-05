BINARY_NAME=opencontext-client

.PHONY: build build-all test clean

build:
	go build -o $(BINARY_NAME) main.go

build-all:
	./build.sh

test:
	go test -v ./...

clean:
	rm -f $(BINARY_NAME)
	rm -f $(BINARY_NAME)-*
