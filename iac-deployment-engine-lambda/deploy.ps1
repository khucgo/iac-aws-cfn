# PowerShell
# .\deploy.ps1 <function_name> <local_aws_named_profile>

$function_name = $args[0]
$aws_profile = $args[1]

echo 'Function: '$function_name
echo 'AWS profile: '$aws_profile

echo '---Start'

echo '---Zipping'
7z a -y $function_name'.zip' .\function\*.py
echo '---Zip done'

echo '---Deploying'
if ($aws_profile) {
    aws lambda update-function-code --function-name $function_name --zip-file fileb://$function_name'.zip' --profile $aws_profile
}
else {
    aws lambda update-function-code --function-name $function_name --zip-file fileb://$function_name'.zip'
}
echo '---Deploy done'

echo '---Cleaning up'
rm .\$function_name'.zip'
echo '---Clean-up done'

echo '---End'