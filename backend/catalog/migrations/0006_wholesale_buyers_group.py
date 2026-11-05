from django.db import migrations


def create_wholesale_buyers_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.using(schema_editor.connection.alias).get_or_create(
        name="Mayoristas aprobados"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("catalog", "0005_product_package_label_product_price_250g_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_wholesale_buyers_group,
            migrations.RunPython.noop,
        ),
    ]
