CFLAGS ?= -O2 -Wall -Wextra
vinyl-stream: vinyl-stream.c fir_taps.h
	$(CC) $(CFLAGS) -o $@ vinyl-stream.c -lasound -lm

clean:
	rm -f vinyl-stream
