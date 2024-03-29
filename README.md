Django Chronicle is an implementation of the slowly changing dimensions type 4
which uses database triggers.

# How to use?

1. Create a custom revision model. e.g.

    ```py
    from chronicle.models import AbstractRevision

    class Revision(AbstractRevision):
        user = models.ForeignKey(settings.AUTH_USER_MODEL)
        created = models.DateTimeField(auto_now_add=True)
    ```

2. Set `settings.REVISION_MODEL` to point to your revision model. e.g.

    ```py
    REVISION_MODEL = 'revision.Revision'
    ```

3. Let your models inherit from `HistoryMixin` e.g.

    ```py
    from chronicle.models import HistoryMixin
    from django.db import models

    class Food(HistoryMixin, models.Model):
        name = models.CharField(max_length=50)
    ```

4. Create all the migrations and run them:

    ```sh
    $ manage.py makemigrations
    $ manage.py migrate
    ```

    That should create all the `_history` tables for your models
    that inherit from the `HistoryMixin`.

5. Create the database triggers

    ```sh
    $ manage.py create_history_triggers
    ```


Now every change to your models should be logged in the `_history` tables
and you can access the model history via the `History` model which becomes
a field of the original class.


# Example usage:

```py
# create
food = Food('Carot')
food.save()
assert(Food.History.objects.filter(id=food.id).count() == 1)

# update
food.name = 'Carrot'
food.save()
assert(Food.History.objects.filter(id=food.id).count() == 2)

# delete
food.delete()
assert(Food.History.objects.filter(id=food.id).count() == 3)
```


# Why database triggers?

The obvious choice to implement model history would be to connect a signal
handler to the `post_save` and `post_delete` signal. This has some rather huge
downsides:

1.) `QuerySet.update()` and a lot of other `QuerySet` methods do not emit any
signals. Having to limit the code to only use `save()` can be a rather huge
performance problem depending on the type of application.

2.) There is a rather large performance impact when creating the history via
the Django ORM. A single `QuerySet.update()` call could result in hundreds
or thousands of inserts. While this could mostly be solved using the
`Manager.bulk_create` method a database trigger is a lot faster as there is no
extra database roundtrip required.

3.) This works for any kind of raw query - even outside of the Django ORM - as
long as the `chronicle.revision_id` session variable is properly set.

The only real downside is the DB compatibility. Right now this package only
supports the PostgreSQL database engine.


# How to issue queries without the Django ORM?

Create a revision by inserting a row into the revision table and set the
`chronicle.revision_id` session variable like so:

```sql
SET chronicle.revision_id = 42; -- replace 42 by the actual revision id
```

Once you have made all changes to your models don't forget to reset the
session variable. Otherwise you might reuse the same revision by accident 
in the same DB session:

```sql
SET chronicle.revision_id TO DEFAULT;
```
