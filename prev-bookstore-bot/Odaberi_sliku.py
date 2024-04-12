import streamlit as st
from myfunc.retrievers import HybridQueryProcessor
import json

st.set_page_config(layout="wide")
st.subheader("Ovo su korice koje poznajemo")
with st.form(key="korice"):
    prompt = st.text_input("Unesi opis korice: ")
    if st.form_submit_button("Pronadji"):
        processor = HybridQueryProcessor(namespace="laguna", top_k=1)
        context, scores = processor.process_query_results(prompt)
        formatted_json_string = '{' + context + '}'
        try:
            book_dict = json.loads(formatted_json_string)
        except json.JSONDecodeError as e:
            print("JSON decoding error:", e)
        # Print values from the dictionary to check
        st.write("Author:", book_dict["book_author"])
        st.write("Book Name:", book_dict["book_name"])
        st.write("Cover Description:", book_dict["book_cover_description"])
        st.image(book_dict["url"])


col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.image("https://laguna.rs/_img/korice/4875/braca_karamazovi_i-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/6232/sutra_je_novi_dan_i_tom_s.jpg")
    st.image("https://laguna.rs/_img/korice/6181/nortengerska_opatija-dzejn_ostin_s.jpg")
    st.image("https://laguna.rs/_img/korice/4628/majstor_i_margarita-mihail_bulgakov_s.jpg")
    st.image("https://laguna.rs/_img/korice/6193/vladalac-nikolo_makijaveli_s.png")
    st.image("https://laguna.rs/_img/korice/5208/zivotinjska_farma-dzordz_orvel_s.jpg")
    st.image("https://laguna.rs/_img/korice/6233/sutra_je_novi_dan_ii_tom_s.jpg")
with col2:
    st.image("https://laguna.rs/_img/korice/6078/burleska_gospodina_peruna_boga_groma-rastko_petrovic_s.jpg")
    st.image("https://laguna.rs/_img/korice/4558/zapisi_iz_podzemlja-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/3635/blago_cara_radovana-jovan_ducic_s.jpg")
    st.image("https://laguna.rs/_img/korice/6233/sutra_je_novi_dan_ii_tom_s.jpg")
    st.image("https://laguna.rs/_img/korice/5764/cica_gorio-onore_de_balzak_s.jpg")
    st.image("https://laguna.rs/_img/korice/4876/braca_karamazovi_ii-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/4579/dozivljaji_toma_sojera-mark_tven_s.jpg")
    
with col3:
    st.image("https://laguna.rs/_img/korice/4427/male_zenedobre_supruge-luiza_mej_olkot_s.jpg")
    st.image("https://laguna.rs/_img/korice/6185/oblomov-ivan_aleksandrovic_goncarov_s.jpg")
    st.image("https://laguna.rs/_img/korice/5839/ponizeni_i_uvredjeni-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/5982/gordost_i_predrasuda-dzejn_ostin_s.png")
    st.image("https://laguna.rs/_img/korice/4432/idiot_i_tom-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/4617/hajduci-branislav_nusic_s.jpg")
    st.image("https://laguna.rs/_img/korice/6232/sutra_je_novi_dan_i_tom_s.jpg")
with col4:
    
    st.image("https://laguna.rs/_img/korice/6185/oblomov-ivan_aleksandrovic_goncarov_s.jpg")
    st.image("https://laguna.rs/_img/korice/6193/vladalac-nikolo_makijaveli_s.png")
    st.image("https://laguna.rs/_img/korice/6181/nortengerska_opatija-dzejn_ostin_s.jpg")
    st.image("https://laguna.rs/_img/korice/6095/gospodin_predsednik-migel_anhel_asturijas_s.jpg")
    st.image("https://laguna.rs/_img/korice/5983/godina_kuge-danijel_defo_s.jpg")
    st.image("https://laguna.rs/_img/korice/6079/drame_1_hasanaginica_i_boj_na_kosovu_s.png")
    st.image("https://laguna.rs/_img/korice/4529/ana_karenjina-lav_tolstoj_s.jpg")
with col5:
    st.image("https://laguna.rs/_img/korice/6080/drame_2_cudo_u_sarganu_i_putujuce_pozoriste_sopalovic_s.png")
    st.image("https://laguna.rs/_img/korice/5982/gordost_i_predrasuda-dzejn_ostin_s.png")
    st.image("https://laguna.rs/_img/korice/6081/odabrane_komedije-jovan_sterija_popovic_s.png")
    st.image("https://laguna.rs/_img/korice/6071/jutra_sa_leutara-jovan_ducic_s.png")
    st.image("https://laguna.rs/_img/korice/5984/mol_flanders-danijel_defo_s.jpg")
    st.image("https://laguna.rs/_img/korice/6025/dnevnik_o_carnojevicu_s.jpg")
with col6:
    st.image("https://laguna.rs/_img/korice/5814/orkanski_visovi-emili_bronte_s.jpg")
    st.image("https://laguna.rs/_img/korice/6000/gradinar-rabindranat_tagore_s.png")
    st.image("https://laguna.rs/_img/korice/5839/ponizeni_i_uvredjeni-fjodor_mihailovic_dostojevski_s.jpg")
    st.image("https://laguna.rs/_img/korice/5849/dvadeset_cetiri_casa_iz_zivota_jedne_zene_i_druge_price-stefan_cvajg_s.png")
    st.image("https://laguna.rs/_img/korice/5838/portret_umetnika_u_mladosti-dzejms_dzojs_s.png")
    st.image("https://laguna.rs/_img/korice/5771/opasne_veze-pjer_soderlo_de_laklo_s.jpg")
    