name 'internshyps_deploy'
description 'For deploying to an already bootstrapped apiserver node'

settings = Chef::EncryptedDataBagItem.load('config', 'config_1')
debug = settings['DEBUG']
domain = settings['DOMAIN']
app_name = settings['APP_NAME']
repo = settings['REPO']
github_user = settings['GITHUB_USER']
github_deploy_key = settings['GITHUB_DEPLOY_KEY']
ec2_host = settings['EC2_HOST']
django_secret_key = settings['DJANGO_SECRET_KEY']
db_host = settings['DB_HOST']
db_port = settings['DB_PORT']
db_name = settings['DB_NAME']
db_username = settings['DB_USERNAME']
db_password = settings['DB_PASSWORD']

default_attributes(
  'app_name' => app_name,
  'repo' => "#{github_user}/#{repo}",
  'github_deploy_key' => github_deploy_key.gsub(/\\n/, "\n"),
  'ec2_host' => ec2_host,
  'django_secret_key' => django_secret_key,
  'database' => {
    'host' => db_host,
    'port' => db_port,
    'name' => db_name,
    'username' => db_username,
    'password' => db_password
  }
)

run_list 'recipe[internshyps::deploy]'
