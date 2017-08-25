Running Bursa
=============

You will need an access key.
We recommend creating an access key specifically for bursa.

Create an access key through the AWS console, under "IAM".
Navigate to the (admin) user to whom the key should be bound,
then in that user's "Security credentials" tab,
under the "Access keys" section,
select the "Create access key" button.

Download the `.csv` file to a safe location
(you may need it again later).
Open the `.csv` to obtain your "access key ID" and "secret access key".

Now you are ready to run bursa:

    python3 bursa $access_key_id $secret_access_key
