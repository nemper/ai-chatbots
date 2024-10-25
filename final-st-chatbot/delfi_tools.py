import pytz
import re
import requests
import xml.etree.ElementTree as ET
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores import Pinecone as LangPine
from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI

from datetime import datetime, time
from openai import OpenAI
from os import getenv
from pinecone_text.sparse import BM25Encoder
from typing import List, Dict, Any, Tuple, Union, Optional
from krembot_db import work_prompts
from krembot_auxiliary import load_matching_tools, connect_to_neo4j, connect_to_pinecone, neo4j_isinstance
from functools import lru_cache
mprompts = work_prompts()
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))



def delfi_api_products(matching_sec_ids: List[int]) -> List[Dict[str, Any]]:
    def get_product_info(token, product_id):
        return requests.get(url="https://www.delfi.rs/api/products", params={"token": token, "product_id": product_id}).content

    # Function to parse the XML response and extract required fields
    def parse_product_info(xml_data):
        product_info = {}
        quantity_discount2_flag = False
        try:
            root = ET.fromstring(xml_data)
            product_node = root.find(".//product")
            if product_node is not None:
                # cena = product_node.findtext('cena')
                lager = product_node.findtext('lager')
                url = product_node.findtext('url')
                id = product_node.findtext('ID')
                navid = product_node.findtext('ID_nav')

                action_node = product_node.find('action')
                if action_node is not None:
                    print(f"Action node found!")  # Debugging line
                    type = action_node.find('type').text
                    if type == "fixedPrice" or type == "fixedDiscount":
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        price_regular_standard = float(action_node.find('priceRegularStandard').text)
                        price_regular_premium = float(action_node.find('priceRegularPremium').text)
                        price_quantity_standard = float(action_node.find('priceQuantityStandard').text)
                        price_quantity_premium = float(action_node.find('priceQuantityPremium').text)

                        if price_regular_standard == price_regular_premium == price_quantity_standard == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard
                        }
                        elif price_regular_standard == price_regular_premium and price_quantity_standard == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska cena sa količinskim popustom': price_quantity_standard
                        }
                        elif price_regular_standard == price_quantity_standard and price_regular_premium == price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena': price_regular_premium
                        }
                        elif price_regular_standard == price_regular_premium == price_quantity_standard != price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena sa količinskim popustom': price_quantity_premium
                        }
                        elif price_regular_standard == price_quantity_standard and price_regular_premium != price_regular_standard and price_quantity_premium != price_quantity_standard and price_regular_premium != price_quantity_premium:
                            akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'akcijska cena': price_regular_standard,
                            'akcijska premium cena': price_regular_premium,
                            'akcijska premium cena sa količinskim popustom': price_quantity_premium
                        }
                        else:
                            akcija = {
                                'naziv akcije': title,
                                'kraj akcije': end_at,
                                'cena sa redovnim popustom': price_regular_standard,
                                'cena sa premium popustom': price_regular_premium,
                                'cena sa redovnim količinskim popustom': price_quantity_standard,
                                'cena sa premium količinskim popustom': price_quantity_premium
                            }
                    elif type == "exponentialDiscount":
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        eksponencijalni_procenti = action_node.find('levelPercentages').text
                        eksponencijalne_cene = action_node.find('levelPrices').text

                        akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'eksponencijalni procenti': eksponencijalni_procenti,
                            'eksponencijalne cene': eksponencijalne_cene
                        }
                    elif type == "quantityDiscount2":
                        quantity_discount2_flag = True
                        title = action_node.find('title').text
                        end_at = action_node.find('endAt').text
                        price_quantity_standard_d2 = float(action_node.find('priceQuantityStandard').text)
                        price_quantity_premium_d2 = float(action_node.find('priceQuantityPremium').text)
                        quantity_discount_limit = int(action_node.find('quantityDiscount2Limit').text)

                        akcija = {
                            'naziv akcije': title,
                            'kraj akcije': end_at,
                            'cena sa redovnim količinskim popustom': price_quantity_standard_d2,
                            'cena sa premium količinskim popustom': price_quantity_premium_d2,
                            'limit za količinski popust': quantity_discount_limit
                        }
                else:
                    print("Action node not found, taking regular price")  # Debugging line
                    # Pristupanje priceList elementu
                price_list = product_node.find('priceList')
                if price_list is not None:
                    collection_price = float(price_list.find('collectionFullPrice').text)
                    full_price = float(price_list.find('fullPrice').text)
                    eBook_price = float(price_list.find('eBookPrice').text)
                    regular_discount_price = float(price_list.find('regularDiscountPrice').text)
                    quantity_discount_price = float(price_list.find('quantityDiscountPrice').text)
                    quantity_discount_limit = int(price_list.find('quantityDiscountLimit').text)
                    premium_discount_price = float(price_list.find('regularDiscountPremiumPrice').text)
                    premium_quantity_discount_price = float(price_list.find('quantityDiscountPremiumPrice').text)
                    premium_quantity_discount_limit = int(price_list.find('quantityDiscountPremiumLimit').text)

                    if regular_discount_price == premium_discount_price == quantity_discount_price == premium_quantity_discount_price:
                        cene = {
                            'akcijska cena': regular_discount_price
                        }
                    elif regular_discount_price == premium_discount_price and quantity_discount_price == premium_quantity_discount_price:
                        cene = {
                            'cena sa popustom': regular_discount_price,
                            'cena sa količinskim popustom': quantity_discount_price
                        }
                    elif regular_discount_price == quantity_discount_price and premium_discount_price == premium_quantity_discount_price:
                        cene = {
                            'cena sa redovnim popustom': regular_discount_price,
                            'cena sa premium popustom': premium_discount_price
                        }
                    elif regular_discount_price == premium_discount_price == quantity_discount_price != premium_quantity_discount_price:
                        cene = {
                            'cena sa popustom': regular_discount_price,
                            'cena sa premium količinskim popustom': premium_quantity_discount_price
                        }
                    elif regular_discount_price == quantity_discount_price and premium_discount_price != regular_discount_price and premium_quantity_discount_price != quantity_discount_price and premium_discount_price != premium_quantity_discount_price:
                        cene = {
                            'cena sa redovnim popustom': regular_discount_price,
                            'cena sa premium popustom': premium_discount_price,
                            'cena sa premium količinskim popustom': premium_quantity_discount_price
                        }
                    else:
                        cene = {
                        'cena sa redovnim popustom': regular_discount_price,
                        'cena sa redovnim popustom na količinu': quantity_discount_price,
                        'cena sa premium popustom': premium_discount_price,
                        'cena sa premium popustom na količinu': premium_quantity_discount_price,
                        }
                    
                    if quantity_discount_limit == quantity_discount_limit:
                        limit = {
                            'limit za količinski popust': quantity_discount_limit
                        }
                    else:
                        limit = {
                            'limit za redovan količinski popust': quantity_discount_limit,
                            'limit za premium količinski popust': premium_quantity_discount_limit
                        }
                
                    pojedinacne_cene_za_quantity_discount2 = {
                        'cena sa redovnim popustom': regular_discount_price,
                        'cena sa premium popustom': premium_discount_price
                    }

                # if lager and int(lager) > 0:
                if int(lager) > 0:
                    product_info = {
                        'puna cena': full_price,
                        'eBook cena': eBook_price,
                        'cena kolekcije': collection_price,
                        'lager': lager,
                        'url': url,
                        'id': id,
                        # 'navid': navid
                    }
                    if action_node is None:
                        product_info.update(cene)
                        product_info.update(limit)
                    elif quantity_discount2_flag:
                        product_info.update(pojedinacne_cene_za_quantity_discount2)
                        product_info.update(akcija)
                    else:
                        product_info.update(akcija)
                else:
                    print(f"Skipping product with lager {lager}")  # Debugging line
            else:
                print("Product node not found in XML data")  # Debugging line
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")  # Debugging line
        return product_info

    # Main function to get info for a list of product IDs
    def get_multiple_products_info(token, product_ids):
        products_info = []
        for product_id in product_ids:
            # print(f"Product ID: {product_id}")
            xml_data = get_product_info(token, product_id)
            # print(f"XML data for product_id {product_id}: {xml_data}")  # Debugging line
            product_info = parse_product_info(xml_data)
            if product_info:
                products_info.append(product_info)
        return products_info

    # Replace with your actual token and product IDs
    token = getenv("DELFI_API_KEY")
    product_ids = matching_sec_ids

    try:
        products_info = get_multiple_products_info(token, product_ids)
    except:
        products_info = "No products found for the given IDs."
    # print(f"API Info: {products_info}")
    # output = "Data returned from API for each searched id: \n"
    # for info in products_info:
    #     output += str(info) + "\n"
    return products_info


def delfi_orders_reply(orders_info: Union[List[Dict[str, Any]], str], tc: List) -> str:
    """
    Maps the values of the order details to a human-readable message.
    """
    def check_if_working_hours():
        belgrade_timezone = pytz.timezone('Europe/Belgrade')
        current_time = datetime.now(belgrade_timezone)

        start_time = time(9, 0)
        end_time = time(16, 45)

        if start_time <= current_time.time() <= end_time:
            return True
        else:
            return False


    def aks_odgovori(orders_dict):
        def extract_timestamp(date_string):
            timestamp = int(date_string[6:-2]) / 1000  # convert milliseconds to seconds
            return datetime.fromtimestamp(timestamp)

        sorted_status_changes = sorted(orders_dict[0]['status_changes'], key=lambda x: extract_timestamp(x['Vreme']))

        try:
            most_recent_status = sorted_status_changes[-1]['StatusOpis']
        except:
            most_recent_status = 'No recent status changes available'
        reply2 = ""
        if most_recent_status == "Kreiranje VIP Naloga":
            reply2 = """
            Vaša porudžbina je spakovana i spremna za slanje. 
            """

        elif most_recent_status == "Preuzimanje Posiljke":
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu. 
            """

        elif most_recent_status == "Ulazak Na Sortirnu Traku":
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu. 
            """

        elif most_recent_status in ["Utovar U Linijski Kamion", "Izlaz iz Magacina"]:
            reply2 = """
            Vaša porudžbina je poslata i biće isporučena u skladu sa rokom za dostavu.
            """

        elif most_recent_status == "Posiljka Na Isporuci":
            reply2 = """
            Vaša porudžbina je poslata i prema podacima koje smo dobili od kurirske službe, nalazi se na isporuci. 
            """

        elif most_recent_status in ["Otkaz isporuke", "Vraceno u magacin"]:
            reply2 = """
            Vaša porudžbina je poslata, ali prema podacima koje smo dobili od kurirske službe, isporuka je otkazana. 
            Prosledićemo urgenciju za isporuku, molimo Vas da proverite da li su podaci sa potvrde o porudžbini ispravni kako bi kurir kontaktirao sa Vama - 
            u ovim situacijama moramo imati povratnu informaciju o prepisci kako bismo poslali urgenciju kurirskoj službi.
            """

        elif most_recent_status == "Unet povrat":
            reply2 = """
            Vaša porudžbina je poslata, ali prema podacima koje smo dobili od kurirske službe, nije bila moguća isporuka, usled čega je paket vraćen pošiljaocu. 
            Ukoliko želite, možemo ponovo poslati porudžbinu, samo je potrebno da nam pošaljete mejl na na imejl-adresu podrska@delfi.rs. 
            """

        elif most_recent_status == "Posiljka Isporucena":
            reply2 = "Posiljka je uspešno isporucena!"
        return reply2

    reply = ""

    slucaj = delfi_check_which_case(orders_info[0])

    if slucaj == 'x24':
        reply = "NEDEFINISAN SLUCAJ PRONADJEN!"

    elif slucaj in ['x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7', 'x8', 'x9', 'x10', 'x11', 'x25', 'x26', 'x27', 'x28', 'x29', 'x30', 'x33']:
        reply = """
        Vaša porudžbina je uspešno kreirana i trenutno se nalazi u fazi obrade. Isporuka će biti realizovana u skladu sa Uslovima korišćenja. 

        Očekivani rok isporuke je 2-5 radnih dana. 
        """

    elif slucaj in ['x12', 'x13']:
        reply = """
        Vaša porudžbina se trenutno nalazi u procesu kreiranja.
        Ukoliko Vam u narednih 30 minuta ne stigne potvrda o kupovini na imejl adresu koju ste ostavili prilikom kreiranja porudžbine molimo Vas da nas kontaktirate slanjem upita na podrska@delfi.rs 
        ili pozivom na broj telefona našeg korisničkog servisa 011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati).
        """

    elif slucaj == 'x14':
        reply = """
        Vaša porudžbina je uspešno kreirana i kupljene naslove možete pronaći u sekciji Moje knjige na Vašem nalogu u okviru EDEN Books aplikacije.

        Ukoliko Vam je potrebna dodatna asistencija molim Vas da nam pošaljete upit na mail podrska@delfi.rs.
        """

    elif slucaj == 'x15':
        reply = """
        Vaša porudžbina nije uspešno realizovana.
        Molimo Vas da nam pošaljete potvrdu o uplati na imejl adresu podrska@delfi.rs ukoliko su sredstva povučena sa Vašeg računa, a da bismo rešili situaciju u najkraćem mogućem roku.
        """

    elif slucaj == 'x16':
        reply = """
        Vaša porudžbina je poslata kurirskom službom DHL i isporuka će biti realizovana u skladu sa Uslovima korišćenja. 

        Očekivani rok isporuke je 2-5 radnih dana. Ukoliko želite, možete pratiti svoju porudžbinu na linku dhl.com. Kod za praćenje je poslati kod koji je upisan u administraciji u okviru porudžbine.
        """

    elif slucaj == 'x22':
        if check_if_working_hours():
            reply = """
            Hvala na poslatom upitu. Slobodan operater će odgovoriti u najkraćem mogućem roku.
            """
        else:
            reply = """
            Hvala na poslatom upitu. Vaša porudžbina je označena kao otkazana.
            Molimo Vas da nam ostavite imejl adresu i/ili kontakt telefon ukoliko se razlikuju u odnosu na podatke iz porudžbine kako bi naš operater kontaktirao sa Vama u najkraćem mogućem roku.
            """

    elif slucaj == 'x23':
        reply = """
        Vaša porudžbina je vraćena u našu knjižaru usled neuspešne isporuke.
        Ona je otkazana pošto nismo dobili povratnu informaciju da li želite da se pošalje ponovo. Molimo Vas da ponovite porudžbinu kako bismo je obradili i poslali.
        """

    elif slucaj in ['x17', 'x18', 'x19', 'x20']:
        reply0 = []
        tc = [x for x in tc if x is not None]
        if len(tc) > 0:
            if "," in tc[0]:
                tc = tc[0].split(",")
                for i in range(len(tc)):
                    reply0.append(delfi_api_aks([tc[i]]))
            else:
                reply0.append(delfi_api_aks(tc))
        reply = aks_odgovori(reply0[0])

    elif slucaj == 'x21':
        reply = """
        Vaša porudžbina je uspešno kreirana i trenutno se nalazi u fazi obrade.
        Kako bi porudžbina bila poslata, potrebno je da pošaljete popunjen formular, koji je poslat u okviru potvrde porudžbine, na adresu Kralja Petra 45, V sprat.
        Molimo Vas da kontaktirate sa nama u vezi sa svim dodatnim pitanjima na broj telefona:  011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati)
        Vaša porudžbina je uspešno kreirana i trenutno se nalazi u fazi obrade.
        Kako bi porudžbina bila poslata, potrebno je da pošaljete popunjen formular, koji je poslat u okviru potvrde porudžbine, na adresu Kralja Petra 45, V sprat.
        Molimo Vas da kontaktirate sa nama u vezi sa svim dodatnim pitanjima na broj telefona:  011/7155-042. Radno vreme našeg korisničkog servisa: ponedeljak-petak (8-17 sati)
        """

    elif slucaj == 'x31':
        reply = """
        Vaša porudžbina je uspešno kreirana i kupljene naslove možete pronaći u sekciji Moje knjige na Vašem nalogu u okviru EDEN Books aplikacije.
        Ukoliko Vam je potrebna dodatna asistencija molim Vas da nam pošaljete upit na mail podrska@delfi.rs.
        """

    elif slucaj == 'x32':
        reply = """
        Vaša porudžbina nije uspešno realizovana. Molimo Vas da nam pošaljete potvrdu o uplati na imejl adresu podrska@delfi.rs ukoliko su sredstva povučena sa Vašeg računa, a da bismo rešili situaciju u najkraćem mogućem roku.
        """

    return reply


def delfi_check_which_case(order_info):
    # x1
    x1 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'WAITING_FOR_EXPORT'
    }
    # x2
    x2 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'WAITING_FOR_MP99'
    }
    # x3
    x3 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'EXPORTED_TO_MP99'
    }
    # x4
    x4 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'EXPORTED'
    }
    # x5
    x5 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'MAIL_SENT'
    }
    # x6
    x6 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'EXPORTED'
    }
    # x7
    x7 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'MAIL_SENT'
    }
    # x8
    x8 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'WAITING_FOR_MP99'
    }
    # x9
    x9 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'EXPORTED_TO_MP99'
    }
    # x10
    x10 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'WAITING_FOR_EXPORT'
    }
    # x11
    x11 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DHL',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'EXPORTED'
    }

    x11 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DHL',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': ['EXPORTED', 'WAITING_FOR_EXPORT']
    }

    x33 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'DELIVERY',
        'package_status': 'CANCELED'
    }

    # x12
    x12 = {
        'type': ['standard', 'ebook'],
        'status': 'readyForOnlinePayment',
        'delivery_service': ['DEFAULT', 'DHL'],
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD']
    }
    # x13
    x13 = {
        'type': ['standard', 'ebook'],
        'status': 'waitingForFinalOnlinePaymentStatus',
        'delivery_service': ['DEFAULT', 'DHL'],
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD']
    }
    # x14
    x14 = {
        'type': 'ebook',
        'status': 'ebookSuccessfullyAdded',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD']
    }
    # x15
    x15 = {
        'type': ['standard', 'ebook'],
        'status': 'canceled',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD']
    }
    # x16
    x16 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DHL',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'INVITATION_SENT'
    }
    # x17
    x17 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'INVITATION_SENT'
    }
    # x18
    x18 = {
        'type': 'standard',
        'status': 'paymentCompleted',
        'delivery_service': 'DEFAULT',
        'payment_type': ['ANY_CREDIT_CARD', 'VISA_PREMIUM_CREDIT_CARD', 'VISA_CREDIT_CARD'],
        'package_status': 'INVITATION_SENT'
    }
    # x19
    x19 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'INVITATION_SENT'
    }
    # x20
    x20 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'ADMINISTRATIVE_BAN',
        'package_status': 'INVITATION_SENT'
    }
    # x21
    x21 = {
        'type': 'standard',
        'status': 'finished',
        'payment_type': 'ADMINISTRATIVE_BAN',
        'package_status': 'WAITING_FOR_EXPORT'
    }
    # x22
    x22 = {
        'type': 'standard',
        'status': 'manuallyCanceled'
    }
    # x23
    x23 = {
        'type': 'standard',
        'status': 'returned'
    }

    x25 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'WAITING_FOR_EXPORT'
    }

    x26 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'WAITING_FOR_MP99'
    }

    x27 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'EXPORTED_TO_MP99'
    }

    x28 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'EXPORTED'
    }

    x29 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DEFAULT',
        'payment_type': 'PAYMENT_SLIP',
        'package_status': 'MAIL_SENT'
    }

    x30 = {
        'type': 'standard',
        'status': 'finished',
        'delivery_service': 'DHL',
        'payment_type': 'ON_DELIVERY',
        'package_status': 'EXPORTED_TO_MP99'
    }

    x31 = {
        'type': 'ebook',
        'status': 'ebookSuccessfullyAdded',
        'delivery_service': 'ONLINE',
    }

    x32 = {
        'type': 'ebook',
        'status': 'canceled',
        'delivery_service': 'ONLINE',
    }


    if (order_info['type'] == x1['type'] and
            order_info['status'] == x1['status'] and
            order_info['delivery_service'] == x1['delivery_service'] and
            order_info['payment_type'] == x1['payment_type'] and
            order_info['package_status'] == x1['package_status']):
        return 'x1'

    elif (order_info['type'] == x2['type'] and
            order_info['status'] == x2['status'] and
            order_info['delivery_service'] == x2['delivery_service'] and
            order_info['payment_type'] == x2['payment_type'] and
            order_info['package_status'] == x2['package_status']):
        return 'x2'

    elif (order_info['type'] == x3['type'] and
            order_info['status'] == x3['status'] and
            order_info['delivery_service'] == x3['delivery_service'] and
            order_info['payment_type'] == x3['payment_type'] and
            order_info['package_status'] == x3['package_status']):
        return 'x3'

    elif (order_info['type'] == x33['type'] and
            order_info['status'] == x33['status'] and
            order_info['delivery_service'] == x33['delivery_service'] and
            order_info['payment_type'] == x33['payment_type'] and
            order_info['package_status'] == x33['package_status']):
        return 'x33'

    elif (order_info['type'] == x4['type'] and
            order_info['status'] == x4['status'] and
            order_info['delivery_service'] == x4['delivery_service'] and
            order_info['payment_type'] == x4['payment_type'] and
            order_info['package_status'] == x4['package_status']):
        return 'x4'
    elif (order_info['type'] == x5['type'] and
            order_info['status'] == x5['status'] and
            order_info['delivery_service'] == x5['delivery_service'] and
            order_info['payment_type'] == x5['payment_type'] and
            order_info['package_status'] == x5['package_status']):
        return 'x5'

    elif (order_info['type'] == x6['type'] and
            order_info['status'] == x6['status'] and
            order_info['delivery_service'] == x6['delivery_service'] and
            order_info['payment_type'] in x6['payment_type'] and
            order_info['package_status'] == x6['package_status']):
        return 'x6'

    elif (order_info['type'] == x7['type'] and
            order_info['status'] == x7['status'] and
            order_info['delivery_service'] == x7['delivery_service'] and
            order_info['payment_type'] in x7['payment_type'] and
            order_info['package_status'] == x7['package_status']):
        return 'x7'

    elif (order_info['type'] == x8['type'] and
            order_info['status'] == x8['status'] and
            order_info['delivery_service'] == x8['delivery_service'] and
            order_info['payment_type'] in x8['payment_type'] and
            order_info['package_status'] == x8['package_status']):
        return 'x8'
    elif (order_info['type'] == x9['type'] and
            order_info['status'] == x9['status'] and
            order_info['delivery_service'] == x9['delivery_service'] and
            order_info['payment_type'] in x9['payment_type'] and
            order_info['package_status'] == x9['package_status']):
        return 'x9'

    elif (order_info['type'] == x10['type'] and
            order_info['status'] == x10['status'] and
            order_info['delivery_service'] == x10['delivery_service'] and
            order_info['payment_type'] in x10['payment_type'] and
            order_info['package_status'] == x10['package_status']):
        return 'x10'

    elif (order_info['type'] == x11['type'] and
            order_info['status'] == x11['status'] and
            order_info['delivery_service'] == x11['delivery_service'] and
            order_info['payment_type'] in x11['payment_type'] and
            order_info['package_status'] in x11['package_status']):
        return 'x11'

    elif (order_info['type'] in x12['type'] and
            order_info['status'] == x12['status'] and
            order_info['delivery_service'] in x12['delivery_service'] and
            order_info['payment_type'] in x12['payment_type']):
        return 'x12'

    elif (order_info['type'] in x13['type'] and
            order_info['status'] == x13['status'] and
            order_info['delivery_service'] in x13['delivery_service'] and
            order_info['payment_type'] in x13['payment_type']):
        return 'x13'

    elif (order_info['type'] == x14['type'] and
            order_info['status'] == x14['status'] and
            order_info['payment_type'] in x14['payment_type']):
        return 'x14'

    elif (order_info['type'] in x15['type'] and
            order_info['status'] == x15['status'] and
            order_info['payment_type'] in x15['payment_type']):
        return 'x15'

    elif (order_info['type'] == x16['type'] and
            order_info['status'] == x16['status'] and
            order_info['delivery_service'] == x16['delivery_service'] and
            order_info['payment_type'] in x16['payment_type'] and
            order_info['package_status'] == x16['package_status']):
        return 'x16'
    
    elif (order_info['type'] == x17['type'] and
            order_info['status'] == x17['status'] and
            order_info['delivery_service'] == x17['delivery_service'] and
            order_info['payment_type'] == x17['payment_type'] and
            order_info['package_status'] == x17['package_status']):
        return 'x17'

    elif (order_info['type'] == x18['type'] and
            order_info['status'] == x18['status'] and
            order_info['delivery_service'] == x18['delivery_service'] and
            order_info['payment_type'] in x18['payment_type'] and
            order_info['package_status'] == x18['package_status']):
        return 'x18'

    elif (order_info['type'] == x19['type'] and
            order_info['status'] == x19['status'] and
            order_info['delivery_service'] == x19['delivery_service'] and
            order_info['payment_type'] == x19['payment_type'] and
            order_info['package_status'] == x19['package_status']):
        return 'x19'

    elif (order_info['type'] == x20['type'] and
            order_info['status'] == x20['status'] and
            order_info['delivery_service'] == x20['delivery_service'] and
            order_info['payment_type'] == x20['payment_type'] and
            order_info['package_status'] == x20['package_status']):
        return 'x20'

    elif (order_info['type'] == x21['type'] and
            order_info['status'] == x21['status'] and
            order_info['payment_type'] == x21['payment_type'] and
            order_info['package_status'] == x21['package_status']):
        return 'x21'

    elif (order_info['type'] == x22['type'] and
            order_info['status'] == x22['status']):
        return 'x22'

    elif (order_info['type'] == x23['type'] and
            order_info['status'] == x23['status']):
        return 'x23'
    
    elif (order_info['type'] == x25['type'] and
            order_info['status'] == x25['status'] and
            order_info['delivery_service'] == x25['delivery_service'] and
            order_info['payment_type'] == x25['payment_type'] and
            order_info['package_status'] == x25['package_status']):
        return 'x25'
    elif (order_info['type'] == x26['type'] and
            order_info['status'] == x26['status'] and
            order_info['delivery_service'] == x26['delivery_service'] and
            order_info['payment_type'] == x26['payment_type'] and
            order_info['package_status'] == x26['package_status']):
        return 'x26'
    elif (order_info['type'] == x27['type'] and
            order_info['status'] == x27['status'] and
            order_info['delivery_service'] == x27['delivery_service'] and
            order_info['payment_type'] == x27['payment_type'] and
            order_info['package_status'] == x27['package_status']):
        return 'x27'
    elif (order_info['type'] == x28['type'] and
            order_info['status'] == x28['status'] and
            order_info['delivery_service'] == x28['delivery_service'] and
            order_info['payment_type'] == x28['payment_type'] and
            order_info['package_status'] == x28['package_status']):
        return 'x28'
    elif (order_info['type'] == x29['type'] and
            order_info['status'] == x29['status'] and
            order_info['delivery_service'] == x29['delivery_service'] and
            order_info['payment_type'] == x29['payment_type'] and
            order_info['package_status'] == x29['package_status']):
        return 'x29'
    elif (order_info['type'] == x30['type'] and
            order_info['status'] == x30['status'] and
            order_info['delivery_service'] == x30['delivery_service'] and
            order_info['payment_type'] == x30['payment_type'] and
            order_info['package_status'] == x30['package_status']):
        return 'x30'
    
    elif (order_info['type'] == x31['type'] and
            order_info['status'] == x31['status'] and
            order_info['delivery_service'] == x31['delivery_service']):
        return 'x31'
    elif (order_info['type'] == x32['type'] and
            order_info['status'] == x32['status'] and
            order_info['delivery_service'] == x32['delivery_service']):
        return 'x32'
    else:
        return 'x24'
    

def delfi_api_orders(order_ids: List[str]) -> Union[List[Dict[str, Any]], str]:
    """
    Retrieves and processes information for a list of order IDs.

    This function fetches detailed information for each order ID by making API requests to an external service.
    It parses the JSON responses to extract relevant order details such as ID, type, status, delivery service,
    delivery time, payment type, package status, and order item type. Additionally, it collects tracking codes
    and performs an auxiliary search if tracking codes are available.

    Args:
        order_ids (List[str]): A list of order IDs for which information is to be retrieved.

    Returns:
        List[Dict[str, Any]] or str: A list of dictionaries containing the extracted order information. If an error
                                     occurs during the retrieval process, it returns an error message indicating that
                                     no orders were found for the given IDs.
    """
    def get_order_info(order_id):
        url = f"http://185.22.145.64:3003/api/order-info/{order_id}"
        headers = {
            'x-api-key': getenv("DELFI_ORDER_API_KEY")
        }
        return requests.get(url, headers=headers).json()
    tc = []
    # Function to parse the JSON response and extract required fields
    def parse_order_info(json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses the JSON data for a single order and extracts relevant order information.

        Args:
            json_data (Dict[str, Any]): The JSON data received from the order information API.

        Returns:
            Dict[str, Any]: A dictionary containing extracted order details such as:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
        """
        order_info = {}
        if 'orderData' in json_data:
            data = json_data['orderData']
            # Extract required fields from the order info
            order_info['id'] = data.get('id', 'N/A')
            order_info['type'] = data.get('type', 'N/A')
            order_info['status'] = data.get('status', 'N/A')
            order_info['delivery_service'] = data.get('delivery_service', 'N/A')
            order_info['payment_type'] = data.get('payment_detail', {}).get('payment_type', 'N/A')
            tc.append(data.get('tracking_codes', None))
            packages = data.get('packages', [])
            if packages:
                package_status = packages[0].get('status', 'N/A')
                order_info['package_status'] = package_status

        return order_info

    # Main function to get info for a list of order IDs
    def get_multiple_orders_info(order_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieves and processes information for multiple order IDs.

        Args:
            order_ids (List[str]): A list of order IDs for which information is to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing details of an order, including:
                - id (str): The unique identifier of the order.
                - type (str): The type of the order.
                - status (str): The current status of the order.
                - delivery_service (str): The delivery service used for the order.
                - delivery_time (str): The estimated delivery time.
                - payment_type (str): The type of payment used.
                - package_status (str): The status of the package.
                - order_item_type (str): The type of items in the order.
            If an error occurs during retrieval, the list may contain an error message string.
        """
        orders_info = []
        for order_id in order_ids:
            json_data = get_order_info(order_id)
            order_info = parse_order_info(json_data)
            if order_info:
                orders_info.append(order_info)
        return orders_info

    # Retrieve order information for all provided order IDs
    try:
        orders_info = get_multiple_orders_info(order_ids)
    except Exception as e:
        print(f"Error retrieving order information: {e}")
        orders_info = "No orders found for the given IDs."

    final_output = delfi_orders_reply(orders_info, tc)

    final_output = delfi_orders_reply(orders_info, tc)
    if final_output.strip() == "":
        return orders_info
    else:
        return f"Prosledi naredni tekst korisniku (nemoj dodavati nikakve druge info): {final_output}" 


def delfi_api_aks(order_ids: List[str]) -> List[Dict[str, Any]]:
    
    def get_order_status(order_id: int) -> Dict[str, Any]:
        url = f"http://www.akskurir.com/AKSVipService/Pracenje/{order_id}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for failed requests
        return response.json()

    def parse_order_status(json_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Parses the JSON data of an order's status and extracts relevant information.

        Args:
            json_data (Dict[str, Any]): The JSON data received from the order tracking API.

        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: 
                - A dictionary containing the error code and current status of the order.
                - A list of dictionaries detailing each status change, including:
                    - 'Vreme' (str): The timestamp of the status change.
                    - 'VremeInt' (str): An internal timestamp or identifier.
                    - 'Centar' (str): The center or location associated with the status.
                    - 'StatusOpis' (str): A description of the status.
                    - 'NStatus' (str): A numerical or coded representation of the status.
        """
        status_info = {}
        status_changes = []
        
        if 'ErrorCode' in json_data and json_data['ErrorCode'] == 0:
            status_info['ErrorCode'] = json_data.get('ErrorCode', 'N/A')
            status_info['Status'] = json_data.get('Status', 'N/A')
            
            lst = json_data.get('StatusList', [])
            for status in lst:
                status_change = {
                    'Vreme': status.get('Vreme', 'N/A'),
                    'VremeInt': status.get('VremeInt', 'N/A'),
                    'Centar': status.get('Centar', 'N/A'),
                    'StatusOpis': status.get('StatusOpis', 'N/A'),
                    'NStatus': status.get('NStatus', 'N/A')
                }
                status_changes.append(status_change)
        else:
            status_info['ErrorCode'] = json_data.get('ErrorCode', 'N/A')
            status_info['Status'] = json_data.get('Status', 'N/A')

        return status_info, status_changes

    def get_multiple_orders_info(order_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Retrieves and processes information for multiple order IDs.

        Args:
            order_ids (List[int]): A list of order IDs for which information is to be retrieved.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing:
                - 'order_id' (int): The unique identifier of the order.
                - 'current_status' (Dict[str, Any]): The current status information of the order, including:
                    - 'ErrorCode' (Any): The error code returned by the API (if any).
                    - 'Status' (Any): The current status of the order.
                - 'status_changes' (List[Dict[str, Any]]): A list of status change records, each containing:
                    - 'Vreme' (str): The timestamp of the status change.
                    - 'VremeInt' (str): An internal timestamp or identifier.
                    - 'Centar' (str): The center or location associated with the status.
                    - 'StatusOpis' (str): A description of the status.
                    - 'NStatus' (str): A numerical or coded representation of the status.
                - 'error' (str, optional): An error message if the order information could not be retrieved.
        """
        orders_info = []
        for order_id in order_ids:
            try:
                # Fetch order status
                order_status_json = get_order_status(order_id)
                current_status, status_changes = parse_order_status(order_status_json)
                
                # Assemble order information
                order_info = {
                    'order_id': order_id,
                    'current_status': current_status,
                    'status_changes': status_changes
                }
                orders_info.append(order_info)
            except requests.exceptions.RequestException as e:
                print(f"HTTP error for order {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
            except Exception as e:
                print(f"Error for order {order_id}: {e}")
                orders_info.append({'order_id': order_id, 'error': str(e)})
        return orders_info

    # Main function to retrieve information for all orders
    try:
        orders_info = get_multiple_orders_info(order_ids)
    except Exception as e:
        print(f"Error retrieving order information: {e}")
        orders_info = "No orders found for the given IDs."

    return orders_info

