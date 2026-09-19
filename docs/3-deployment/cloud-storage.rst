.. _cloud-storage:

Configuring cloud storage
=========================

.. index:: storage, S3

If you generated the project with ``cloud_provider=AWS``, static files and user uploads are served from S3 rather than from your application server. This is independent of the platform you deploy to, so follow this page alongside the deployment guide of your choice.

The template configures django-storages' S3 backend, so any S3-compatible service works as well: set ``AWS_S3_ENDPOINT_URL`` in ``config/settings/production.py`` and follow your provider's equivalent of the bucket policy below.

How the template uses your bucket
---------------------------------

A single bucket holds both kinds of files, under two prefixes:

- ``static/``: the output of ``collectstatic``, meant to be **publicly readable**.
- ``media/``: user uploads, served through ``MEDIA_URL``.

The storage does **not** set a per-object ACL on upload. Uploaded objects simply inherit whatever access rules the bucket has, so making static files reachable is a one-off bucket configuration step, described below. This matches S3's current default, which is to disable per-object ACLs in favour of bucket-wide policies.

.. warning:: The instructions below deliberately expose only the ``static/`` prefix. Granting public read on the whole bucket also exposes ``media/``, and since the template sets unsigned URLs for media, every user upload would then be readable by anyone able to guess its URL. See `Keeping media private`_ if uploads in your project are not meant to be public.

Amazon S3
---------

New buckets have ACLs disabled (*Object Ownership: bucket owner enforced*) and all four **Block Public Access** settings enabled. You need to relax the two policy-related ones, then attach a bucket policy scoped to the ``static/`` prefix.

.. code-block:: bash

    BUCKET=your-bucket-name

    # Outside of us-east-1, add:
    #   --create-bucket-configuration LocationConstraint=$AWS_REGION
    aws s3api create-bucket --bucket $BUCKET --region us-east-1

    # Allow public *policies*, while still blocking public ACLs
    aws s3api put-public-access-block --bucket $BUCKET \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false"

    cat > /tmp/static-policy.json <<EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "PublicReadForStaticFiles",
          "Effect": "Allow",
          "Principal": "*",
          "Action": "s3:GetObject",
          "Resource": "arn:aws:s3:::$BUCKET/static/*"
        }
      ]
    }
    EOF

    aws s3api put-bucket-policy --bucket $BUCKET --policy file:///tmp/static-policy.json

The same can be done from the console, under the bucket's **Permissions** tab: first edit **Block public access**, then **Bucket policy**. S3 will label the bucket as *Publicly accessible* afterwards, which is expected.

The policy applies to objects already in the bucket, so there is no need to re-run ``collectstatic``.

.. note:: Requests for a key that does not exist return ``403 Forbidden`` rather than ``404 Not Found``, because anonymous callers lack ``s3:ListBucket``. If static files still 403 after this, check the object is really there with ``aws s3api head-object --bucket $BUCKET --key static/css/tailwind.css``.

.. note:: Static files keep their names on S3, and ``AWS_S3_OBJECT_PARAMETERS`` lets browsers cache them for a week. The stylesheet is built from the class names in use, so it changes with most deployments, and a returning visitor can be served new markup with the stylesheet of the deployment before. Shorten that cache, or serve the static files with hashed names (WhiteNoise does, and so does a manifest storage on S3), before the first visitors arrive.

Keeping media private
---------------------

Making ``static/`` public is expected: those files ship with your application. User uploads are a different matter, and the template's defaults assume they are public.

``AWS_QUERYSTRING_AUTH = False`` in ``config/settings/production.py`` makes ``media`` URLs unsigned and permanent. If uploads in your project are sensitive, remove that setting so django-storages returns time-limited signed URLs, and do not extend any public bucket policy to the ``media/`` prefix.

Serving through a CDN
---------------------

Putting a CDN in front of the bucket lets you keep it entirely private, since the CDN authenticates to the origin on your behalf: CloudFront with an `Origin Access Control`_. Once the distribution is set up, point ``DJANGO_AWS_S3_CUSTOM_DOMAIN`` at it so generated URLs use the CDN domain.

.. _Origin Access Control: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
