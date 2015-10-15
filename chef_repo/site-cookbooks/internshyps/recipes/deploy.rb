include_recipe 'application'

app_domain = node['app_domain']
django_secret_key = node['django_secret_key']
database_settings = node['database']
upload_settings = node['upload']

application 'internshyps' do
  path '/srv/internshyps'
  owner 'deploy'
  group 'nogroup'
  repository "git@github.com:#{node.repo}.git"
  revision 'master'
  deploy_key node['github_deploy_key']
  migrate true

  django do
    requirements 'requirements/requirements.txt'
    debug false
    collectstatic true
    secret_key django_secret_key
    app_domain app_domain
    upload upload_settings
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
