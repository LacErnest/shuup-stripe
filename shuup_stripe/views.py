# -*- coding: utf-8 -*-
# This file is part of Shuup Stripe Addon.
#
# Copyright (c) 2012-2018, Shoop Commerce Ltd. All rights reserved.
#
# This source code is licensed under the OSL-3.0 license found in the
# LICENSE file in the root directory of this source tree.
from logging import getLogger

import stripe
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.base import View
from shuup.front.views.dashboard import DashboardViewMixin

from shuup_stripe.models import StripeCustomer
from shuup_stripe.utils import get_stripe_processor

LOGGER = getLogger(__name__)


class StripeSavedPaymentInfoView(DashboardViewMixin, TemplateView):
    template_name = "shuup/stripe/saved_payment_info.jinja"

    def post(self, request, *args, **kwargs):
        stripe_processor = get_stripe_processor(request)
        stripe_token = request.POST.get("stripeToken")
        stripe_customer = None

        if stripe_token:
            stripe.api_key = stripe_processor.secret_key
            stripe_customer = StripeCustomer.objects.filter(contact=self.request.customer).first()

            try:
                if stripe_customer:
                    stripe.Customer.modify(stripe_customer.customer_token, source=stripe_token)
                else:
                    customer = stripe.Customer.create(source=stripe_token, email=request.customer.email)
                    stripe_customer = StripeCustomer.objects.create(
                        contact=self.request.customer,
                        customer_token=customer.id
                    )

            except stripe.StripeError:
                LOGGER.exception("Failed to create Stripe Customer")
                stripe_customer = None

        if stripe_customer:
            messages.success(request, _("Payment details successfully saved."))
        else:
            messages.error(request, _("Error while saving payment details."))

        return HttpResponseRedirect(reverse("shuup:stripe_saved_payment"))

    def get_context_data(self, **kwargs):
        context = super(StripeSavedPaymentInfoView, self).get_context_data(**kwargs)
        stripe_processor = get_stripe_processor(self.request)
        stripe_customer = StripeCustomer.objects.filter(contact=self.request.customer).first()

        context["stripe_customer"] = stripe_customer
        context["customer"] = self.request.customer
        context["stripe_processor"] = stripe_processor

        if stripe_customer:
            stripe.api_key = stripe_processor.secret_key

            try:
                customer = stripe.Customer.retrieve(stripe_customer.customer_token)
                context["stripe_customer_data"] = customer.to_dict()
            except stripe.StripeError:
                pass

        return context


class StripeDeleteSavedPaymentInfoView(View):
    def post(self, request, *args, **kwargs):
        stripe_processor = get_stripe_processor(request)
        stripe_customer = StripeCustomer.objects.filter(contact=self.request.customer).first()
        source_id = request.POST.get("source_id")

        if stripe_customer and source_id:
            stripe.api_key = stripe_processor.secret_key

            try:
                customer = stripe.Customer.retrieve(stripe_customer.customer_token)
                customer.sources.retrieve(source_id).delete()
            except stripe.StripeError:
                LOGGER.exception("Failed to delete Stripe source")
                messages.error(request, _("Unknown error while removing payment details."))

            else:
                messages.success(request, _("Payment successfully removed."))

        return HttpResponseRedirect(reverse("shuup:stripe_saved_payment"))
