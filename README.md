# Stackd IAC

IAC stack

## Installation

~~~
$ pip install stackdiac
~~~

## Usage

### initializing project

~~~
$ stackd create
~~~

Add --help for usage message. Initalizes new project in current directory. Clones core specifications,
terraform provider versions, setups vault. 

## Updating binaries and repos

~~~
$ stackd update
~~~

binaries and repos will be synced with stackd.yaml project file

## Building infrastructure code

~~~
$ stackd build
~~~

Builds IAC specifications for all configured clusters

## running terragrunt plan

`stackd tg` uses builded module path as target argument

~~~
$ stackd tg ./build/<cluster>/<stack>/<module> <command> <args>
~~~

add -b to build before run terragrunt

~~~
$ stackd tg -b build/data/sys/nodes/ plan
$ stackd tg -b build/data/sys/nodes/ apply
$ stackd tg -b build/data/sys/nodes/ output
~~~

## running operations

~~~
stackd op -b data/sys/deploy
~~~

configuration is stack-scoped. running `terragrunt run-all <op.command>` on operations's modules list.
target is `<cluster>/<stack>/<operation>` form, not a path

example: upgrading kubernetes:

- adjust k8s version in cluster vars, kubernetes_version
- run upgrade operation

~~~
$ stackd op -b data/sys/upgrade
~~~

## available commands

~~~
$ stackd

Usage: stackd [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  build
  create
  op
  tg
  ui
  update
~~~
