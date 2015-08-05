name 'internshypes_load_balancer'
description 'A node running Nginx as a load balancer'

default_attributes('nginx' => { 'pid' => '/run/nginx.pid' })

run_list 'recipe[internshyps]'
