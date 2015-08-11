include_recipe 'application'

django_secret_key = node['django_secret_key']
database_settings = node['database']

# user 'deploy' do
#   system true
#   shell '/bin/false'
# end

# directory '/srv/internshyps/shared' do
#   recursive true
#   action :create
# end

application 'internshyps' do
  path '/srv/internshyps'
  owner 'deploy'
  group 'nogroup'
  repository "git@github.com:#{node.repo}.git"
  revision 'master'
  deploy_key node['github_deploy_key']
  migrate true
  # packages ['libpq-dev', 'python-dev', 'gcc']

  django do
    requirements 'requirements/requirements.txt'
    debug true
    collectstatic true
    secret_key django_secret_key
    database do
      host database_settings['host']
      port database_settings['port']
      database database_settings['name']
      adapter 'postgresql_psycopg2'
      username database_settings['username']
      password database_settings['password']
    end
  end
end
