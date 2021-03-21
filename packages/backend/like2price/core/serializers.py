import json
from web3.auto import w3
from hexbytes import HexBytes
from eth_account.messages import encode_defunct

from rest_framework import serializers
from django.http import Http404

from like2price.core.models import (
    Artist,
    Item,
    Sign,
)
from ipfs_utility.core import (
    create_item_folder,
    like,
    dislike,
    follow,
)


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = (
            '__all__'
        )


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = (
            '__all__'
        )


class CreateItemSerializer(serializers.ModelSerializer):
    nft_id = serializers.CharField()
    nft_address = serializers.CharField()
    wallet_address = serializers.CharField(
        source='owner.wallet_address', write_only=True)

    class Meta:
        model = Item
        fields = (
            '__all__'
        )
        read_only_fields = (
            "owner",
            "ipns",
        )

    def create(self, validated_data):
        if not validated_data.get('owner'):
            raise Http404('wallet_address not exists.')
        artist, _ = Artist.objects.get_or_create(
            wallet_address=validated_data.get('owner').get("wallet_address"))
        validated_data["owner"] = artist
        item_instance = super().create(validated_data)
        ipns = create_item_folder(validated_data["nft_address"])
        try:
            item_instance.ipns = ipns
            item_instance.save()
        except Exception as e:
            print(e)
        return item_instance


class CreateSignSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sign
        fields = (
            '__all__'
        )
        read_only_fields = (
            "ipns",
        )

    def create(self, validated_data):
        sign_type = validated_data.get('type')
        item = validated_data.get("item")
        self.verify_sign(validated_data.get('address'),
                         json.dumps(validated_data.get('msg')),
                         validated_data.get('sig'))

        response = super().create(validated_data)
        sign_instance = response
        try:
            if sign_type == "likes":
                item.likes += 1
                sign_instance.ipns = like(sign_instance.id, publish=True)
            elif sign_type == "dislikes":
                item.dislikes += 1
                sign_instance.ipns = dislike(sign_instance.id, publish=True)
            elif sign_type == "followers":
                item.followers += 1
                sign_instance.ipns = follow(sign_instance.id, publish=True)
            sign_instance.save()
        except Exception as e:
            print(e)
        item.save()
        return sign_instance

    @classmethod
    def verify_sign(cls, address, msg, signature):
        assert isinstance(msg, str), 'msg must be str'
        message = encode_defunct(text=msg)
        signature_bytes = HexBytes(signature)
        recovered_addr = w3.eth.account.recover_message(message, signature=signature_bytes)
        if recovered_addr != address:
            raise serializers.ValidationError('recovered addresss not match')


class PriceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    price = serializers.FloatField()
