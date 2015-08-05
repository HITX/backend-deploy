include_recipe 'application'

database_settings = node['database']
# mig_command = 'sudo /srv/save/shared/env/bin/python manage.py syncdb --noinput'

directory '/srv/save/shared' do
  recursive true
  action :create
end

application 'save' do
  # only_if { node['roles'].include? 'save_application_server' }
  path '/srv/save'
  owner 'nobody'
  group 'nogroup'
  repository "https://github.com/#{node.repo}.git"
  revision 'master'
  migrate true
  packages ['libpq-dev', 'python-dev', 'gcc']
  # packages ["libpq-dev", "git-core", "mercurial"]

  django do
    only_if { node['roles'].include? 'save_application_server' }
    # packages ["redis"]
    # migration_command mig_command
    requirements 'requirements/requirements.txt'
    debug true
    collectstatic true
    database do
      host database_settings['host']
      port database_settings['port']
      database database_settings['name']
      adapter 'postgresql_psycopg2'
      username database_settings['username']
      password database_settings['password']
    end
  end

  gunicorn do
    only_if { node['roles'].include? 'save_application_server' }
    app_module :django
  end

  nginx_load_balancer do
    only_if { node['roles'].include? 'save_load_balancer' }
    application_port 8080
    static_files "/static" => "static"
  end
end
