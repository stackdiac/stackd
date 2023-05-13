
PROJECT_PATH=testiac

clean:
	rm -fR ${PROJECT_PATH}

create: clean
	mkdir -p ${PROJECT_PATH}
	poetry run stackd create -f -p ${PROJECT_PATH} -d test.link -n testproj --vault-address=127.0.0.1\
		-t "test proj"
	ln -svr ../../../v10/infra/devops-terraform/cluster/data.yaml ./testiac/cluster/data.yaml

ui:
	cd ../stackd-ui && make build
	cp -vR ../stackd-ui/dist/* ./stackdiac/ui/