# How to add support for a new language

## The optimal way

To add support for a new language, first of all you need to create a [fork of the project](https://github.com/vmakeev/huawei_mesh_router/fork).

Next, create a copy of the file [`custom_components/huawei_mesh_router/translations/en.json`](../custom_components/huawei_mesh_router/translations/en.json) and give it a name `<your_language_code>.json`. The new file should also be located in the [`custom_components/huawei_mesh_router/translations/`](../custom_components/huawei_mesh_router/translations/) folder. After that, translate all the values in the json file into your language.

_Note: The language codes follow the [BCP47](https://www.rfc-editor.org/info/bcp47) format, a few examples can be seen [here](https://gist.github.com/typpo/b2b828a35e683b9bf8db91b5404f1bd1)._

After that, you will need to make a [pull request](https://docs.github.com/articles/about-pull-requests) to the [original project](https://github.com/vmakeev/huawei_mesh_router), I will check it and add your language to the list of supported.

## A simpler, but less technological way

Download the [`en.json` file](../custom_components/huawei_mesh_router/translations/en.json), translate all the values into the language of your choice, and [create an issue](https://github.com/vmakeev/huawei_mesh_router/issues/new/choose) to add a new language. 

Be sure to attach the translated file to the issue and specify which language it is, so that there are no misunderstandings.

After checking, I will add a new translation to the component.
