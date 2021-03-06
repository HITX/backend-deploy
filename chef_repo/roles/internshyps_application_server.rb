name 'internshyps_application_server'
description 'A node hosting a running Django/gunicorn process'

settings = Chef::EncryptedDataBagItem.load('config', 'config_1')
debug = settings['DEBUG']
app_domain = settings['APP_DOMAIN']
app_name = settings['APP_NAME']
repo = settings['REPO']
github_user = settings['GITHUB_USER']
github_deploy_key = settings['GITHUB_DEPLOY_KEY']
ec2_host = settings['EC2_HOST']
django_secret_key = settings['DJANGO_SECRET_KEY']
upload_access_key = settings['UPLOAD_ACCESS_KEY']
upload_secret_key = settings['UPLOAD_SECRET_KEY']
upload_media_bucket = settings['UPLOAD_MEDIA_BUCKET']
upload_static_bucket = settings ['UPLOAD_STATIC_BUKET']
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
  'app_domain' => app_domain,
  'django_secret_key' => django_secret_key,
  'upload' => {
    'aws_access_key' => upload_access_key,
    'aws_secret_key' => upload_secret_key,
    'aws_media_bucket' => upload_media_bucket,
    'aws_static_bucket' => upload_static_bucket
  },
  'database' => {
    'host' => db_host,
    'port' => db_port,
    'name' => db_name,
    'username' => db_username,
    'password' => db_password
  }
)

# run_list('recipe[build-essential]', 'recipe[internshyps]')
run_list 'recipe[internshyps]'
