import graphene
from graphene_django import DjangoObjectType
from apps.hrmn.models import Employee


class EmployeeType(DjangoObjectType):
    class Meta:
        model = Employee
        fields = (
            'id',
            'username',
            'name_lastname',
            'n_document',
            'charge',
            'subsidiary',
            'date_birth',
            'phone',
            'email',
            'is_enabled',
            'foto'
        )
        exclude = ('password', 'user_permissions', 'groups', 'is_superuser')

    foto_url = graphene.String()

    def resolve_foto_url(self, info):
        if self.foto:
            return info.context.build_absolute_uri(self.foto.url)
        return None