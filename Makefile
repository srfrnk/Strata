.PHONY: build run

build:
	docker build -t strata --build-arg CUDA_ARCHITECTURES=86 .

patch-vram:
	docker run --rm -v strata-data:/data alpine sh -c "\
		apk add --no-cache jq && \
		jq '.args += [\"--vram-reserve-mib\", \"2048\"]' /data/config/strata-coder-iq1_m.json > /tmp/patched.json && \
		mv /tmp/patched.json /data/config/strata-coder-iq1_m.json"

run:
	docker run --rm --gpus all \
		-p 8080:8080 \
		--ulimit memlock=-1 \
		-v strata-data:/data \
		-e FAMILY=coder \
		-e MODEL=IQ1_M \
		-e CONTEXT=131072 \
		-e KV=int8 \
		-e VISION=yes \
		--stop-timeout 60 \
		strata
