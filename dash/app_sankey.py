# synpuff.ipynb content
import pandas as pd
pd.set_option("display.max_rows", None, "mode.chained_assignment", None)
from itertools import chain

import numpy as np
import datetime as dt

from dash import Dash, html, dcc, Input, Output, State, callback, callback_context
import plotly.express as px
import plotly
import plotly.offline
import plotly.graph_objs as go

'''Georgie's code'''
# copy the data to your drive and then modify this path as required

folder = 'synpuff/'

# base query for generating the cohort
person = pd.read_csv('../synpuff/person.csv')
condition_occurrence = pd.read_csv('../synpuff/condition_occurrence.csv')
drug_exposure = pd.read_csv('../synpuff/drug_exposure.csv')
concept = pd.read_csv('../synpuff/concept.csv')
hierarchy = pd.read_csv('../synpuff/hierarchy.csv')
props = pd.read_csv('../synpuff/hemonc_component_properties.csv')

neoplasm_codes = [44832128,44834489,44834490,44819488,44826452,44825256,
                  44836837,
                  44822871, 44825197, 44820602, 44835672,
                  44829798, 44828730]
condition_occurrence=condition_occurrence.loc[condition_occurrence['condition_source_concept_id'].isin(neoplasm_codes)]

'''Ivy's code'''
#rxnorm = props[props['vocabulary_id']=='RxNorm']
#list of valid drug categories from Ivy from RxNorm/HemOnc
sact=['Alkylating agent', 'Anti-CD38 antibody', 'Anti-CTLA-4 antibody', 'Anti-TACSTD2 antibody-drug conjugate', 'Anthracycline', 'Antiandrogen', 'Antifolate',
'Antimetabolite', 'Antitumor antibiotic', 'Anti-CD52 antibody', 'Anti-CD20 antibody', 'Anti-EGFR antibody', 'Anti-HER2 antibody', 'Anti-CD38 antibody', 'Anti-PD-1 antibody',
'Anti-PD-L1 antibody', 'Anti-RANKL antibody', 'Anti-SLAMF7 antibody','Anti-VEGF antibody', 'Aromatase inhibitor', 'Aromatase inhibitorsthird generation',
'Biosimilar', 'BRAF inhibitor', 'DNA methyltransferase inhibitor', 'Deoxycytidine analog', 'EGFR inhibitor', 'ERBB 2 inhibitor', 'Estrogen receptor inhibitor',
'Folic acid analog', 'Fluoropyrimidine', 'GnRH agonist', 'HDAC inhibitor', 'Human DNA synthesisinhibitor', 'Microtubule inhibitor', 'MTOR inhibitor',
'Nitrogen mustard', 'Nitrosourea', 'Neutral', 'PARP inhibitor', 'PARP1 inhibitor', 'PARP2 inhibitor', 'Phenothiazine', 'Platinum agent', 'Proteasome inhibitor',
'Purine analog', 'Pyrimidine analog', 'RANK ligand inhibitor', 'Selective estrogen receptor modulator', 'Somatostatin analog', 'T-cell activator',
'Targeted therapeutic', 'Taxane', 'Topoisomerase I inhibitor', 'Topoisomerase II inhibitor', 'Triazene', 'Vinca alkaloid', 'Xanthine oxidase inhibitor',
'WHO Essential Cancer Medicine']
#rxnorm = rxnorm[rxnorm['component_class_name'].isin(sact)]
props=props[props['component_class_name'].isin(sact)]
antican = props['concept_id_2']
drug_exposure=drug_exposure[drug_exposure['drug_concept_id'].isin(antican)]
#rxnorm['component_class_name'].value_counts()

# make labels from mapping concept IDs to concept labels
concept_lookup = {c.concept_id: c.concept_name for c in concept.itertuples()}

def make_labels(df):
    for c in df.columns:
        if 'concept_id' in c:
            df[c.replace('_id', '_label')] = df[c].map(concept_lookup)
        if 'concept_id' in c or 'source' in c or len(df[df[c].notna()])==0:
            df = df.drop(c, axis=1)
    return df

condition_occurrence_labelled = make_labels(condition_occurrence)
drug_exposure_labelled = make_labels(drug_exposure)
person_labelled = make_labels(person)

'''Applying extra filters to drug df'''
drug_exposure_labelled['drug_exposure_year'] = pd.to_datetime(drug_exposure_labelled['drug_exposure_start_date'], format='%Y-%m-%d').dt.year
exclusions = ['dexamethasone', 'filgrastim', 'epoetin alfa', 'methylprednisolone', 'hydrocortisone', 'octreotide']
drug_exposure_labelled=drug_exposure_labelled[~drug_exposure_labelled['drug_concept_label'].isin(exclusions)]

'''Data Linkage'''
person_labelled_small= person_labelled.loc[:,['person_id', 'year_of_birth', 'gender_concept_label']]
drug_persons = pd.merge(drug_exposure_labelled, person_labelled_small, on='person_id', how='left')
drug_persons['age_at_treatment'] = drug_persons['drug_exposure_year'] - drug_persons['year_of_birth']
#condition linkage
condition_labelled_small= condition_occurrence_labelled.loc[:,['person_id', 'condition_concept_label']]
condition_labelled_small['occ_number'] = 'cond_' + (condition_labelled_small.groupby('person_id').cumcount()).astype(str) 
cond_pivot = condition_labelled_small.pivot(index='person_id', columns='occ_number', values='condition_concept_label').reset_index()
drug_persons = pd.merge(drug_persons, cond_pivot, on='person_id', how='left')
'''Reshaping dataframe'''
#reduce DF down to relevant variables for the visualization
small = drug_persons[['person_id', 'drug_exposure_start_date', 'drug_concept_label', 'drug_exposure_year', 'gender_concept_label', 'age_at_treatment', 'cond_0', 'cond_1', 'cond_2', 'cond_3']]
#small = pd.merge(small, cond_pivot, on='person_id', how='left')
#small = small.dropna()
small = small.drop_duplicates()
small_sorted = small.sort_values('drug_concept_label')
#small['drug_concept_label'] = small_sorted.groupby(['person_id', 'drug_exposure_start_date'])['drug_concept_label'].transform(lambda x : ' & '.join(x))
#small.head()
small_nodup = small_sorted.drop_duplicates()
#small_nodup['drug_concept_label']=small_nodup['drug_concept_label'].str.replace('& ', '&<br>')

# add new variable for every new drug administration per person
readministrations = pd.Series(np.zeros(len(small_nodup),dtype=int),index=small_nodup.index)

# Loop through all unique ids                                                                                                                                                                                      
all_id = small_nodup['person_id'].unique()
id_administrations = {}
for pid in all_id:
    # These are all the times a patient with a given ID has had surgery                                                                                                                                            
    patient = small_nodup.loc[small_nodup['person_id']==pid]
    administrations_sorted = pd.to_datetime(patient['drug_exposure_start_date'], format='%Y-%m-%d').sort_values()

# This checks if the previous surgery was longer than 180 days ago                                                                                                                                              
    frequency = administrations_sorted.diff()<dt.timedelta(days=6000)

    # Compute the readmission                                                                                                                                                                                      
    n_administrations = [0]
    for v in frequency.values[1:]:
       n_administrations.append((n_administrations[-1]+1)*v)

    # Add these value to the time series                                                                                                                                                                           
    readministrations.loc[administrations_sorted.index] = n_administrations

small_nodup['readministration'] = readministrations
small_nodup['drug_concept_label'] = small_nodup['drug_concept_label'] + (small_nodup['readministration'].apply(lambda x: x*' '))

#pivot the DF from long to wide
pivoted = small_nodup.pivot(index='person_id', columns='readministration', values='drug_concept_label').reset_index()
# add the prefix 'drug' to every instance
prefixed = pivoted.add_prefix('drug')
#remove the word 'drug' from other variables
df = prefixed.rename(columns={"drugperson_id": "person_id", "readministration":"index"})
df.sort_values('drug0')
#add a value of 1 to all data points for sums in the visualization
df["count"] = 1

'''vis'''

#colorPalette = ['#fde725','#7ad151', '#22a884', '#2a788e', '#414487', '#440154']

#sankey generation from ken lok on Medium
def genSankey(df, cat_cols=[], value_cols='', title='Sankey Diagram'):
    #color palette
    #skip
    labelList = []
    colorNumList = []
    colorList = []
    for catCol in cat_cols:
        labelListTemp = list(set(df[catCol].dropna().values))
        colorNumList.append(len(labelListTemp))
        labelList = labelList + labelListTemp
    #remove duplicates from labelList
    labelList = list(dict.fromkeys(labelList))

    '''labelList2 = labelList.copy()
    for i in range(len(labelList2)):
        if labelList2[i] == labelList2[i]:
            labelList2[i] = (labelList2[i])[:3]
    
    #print(labelList2)
    colorlist = np.unique(labelList2, return_inverse=1)[1].tolist()
    for i in range(len(colorlist)):
        if colorlist[i] == colorlist[i]:
            colorlist[i] = colorlist[i]%26
    #print(colorlist)'''
    
    #define colors based on number of levels
    '''colorList = []
    for idx, colorNum in enumerate(colorNumList):
        colorList = colorList + [colorPalette[idx]]*colorNum'''

    
    colorList = labelList.copy()
    for i in range(len(colorList)):
        if colorList[i] == colorList[i]:
            colorList[i] = px.colors.qualitative.Alphabet[((ord((colorList[i])[:1]))+(ord((colorList[i])[1])))%26]
    

    #transform df into asource-target pair
    for i in range(len(cat_cols)-1):
        if i==0:
            sourceTargetDf = df[[cat_cols[i], cat_cols[i+1], value_cols]]
            sourceTargetDf.columns = ['source', 'target', 'count']
        else:
            tempDf = df[[cat_cols[i], cat_cols[i+1], value_cols]]
            tempDf.columns = ['source', 'target', 'count']
            sourceTargetDf = pd.concat([sourceTargetDf, tempDf])
        sourceTargetDf = sourceTargetDf.groupby(['source','target']).agg({'count':'sum'}).reset_index()
    
    #add index for source-target pairs
    sourceTargetDf['sourceID'] = sourceTargetDf['source'].apply(lambda x:labelList.index(x))
    sourceTargetDf['targetID'] = sourceTargetDf['target'].apply(lambda x:labelList.index(x))
  
    nodes = np.unique(sourceTargetDf[["sourceID", "targetID"]], axis=None)
    nodes = pd.Series(index=nodes, data=range(len(nodes)))


    #sankey format/color specs by Rob Raymond on StackOverflow
    fig = go.Figure(
        go.Sankey(
            node = {
                "label": labelList,
                "color": colorList,
                    #[
                    #px.colors.qualitative.Set1[df[''] % 9]
                    #for i in nodes
                    #px.colors.qualitative.Alphabet[ord((labelList[i])[:1])%26]
                    #for i in nodes
                #]
            },
            link = {
                "source": sourceTargetDf["sourceID"],
                "target": sourceTargetDf["targetID"],
                "value": sourceTargetDf["count"]
                #,
                #"color": [
                    #px.colors.qualitative.Pastel1[df[''] % 9]
                    #for i in nodes.loc[sourceTargetDf["sourceID"]]
                    #px.colors.qualitative.Pastel1[colorlist]
                    #for i in nodes.loc[sourceTargetDf["sourceID"]]
                #],
            },
        )
    )

    return fig

'''dash'''
app = Dash(__name__)

drugoptions = ['cyclophosphamide',
               'paclitaxel',
               'doxorubicin',
               'leuprolide',
               'azacitidine',
               'triptorelin',
               'methotrexate']

options = ['Malignant neoplasm of nipple and areola of female breast',
            'Malignant neoplasm of axillary tail of female breast',
            'Malignant neoplasm of other specified sites of female breast',
            'Carcinoma in situ of breast',
            'Malignant neoplasm of head of pancreas',
            'Malignant neoplasm of body of pancreas',
            'Malignant neoplasm of tail of pancreas',
            'Malignant neoplasm of pancreatic duct',
            'Malignant neoplasm of other specified sites of pancreas',
            'Malignant neoplasm of pancreas, part unspecified',
            'Malignant neoplasm of ovary']

app.layout = html.Div(children=[
    html.H1(children='Sankey', style={'textAlign':'center'}),

    #Left menu 1
    html.Div([
        html.B(children='First Drug', style={'textAlign':'left'}),
        # first treatment
        dcc.Checklist(
            drugoptions,
            ['doxorubicin','cyclophosphamide'],
        id='first_treatment'
        ),
        html.Br(),
        dcc.Checklist(
            [{"label":"Select all drugs", "value":"Alldrugs"}],
            value=[],
            id='all_drugs_or_none'
            )
    ], style={'display':'inline-block', 'width':'10%'}),

    #Left menu 2
    html.Div([
        html.B(children='Sex', style={'textAlign':'left'}),
        dcc.Checklist(
            ['MALE', 'FEMALE'],
            ['MALE', 'FEMALE'],
        id='person_gender'
        ),
        html.B(children='Age at treatment', style={'textAlign':'left'}),
        dcc.RangeSlider(min=26, max=101, value=[26, 101],
        id='age_at_treatment',
        tooltip={
            "always_visible": False
        }
        ),
        html.B(children='Treatment Year', style={'textAlign':'left'}),
        dcc.Checklist(
            [2007, 2008, 2009, 2010],
            [2007, 2008, 2009, 2010],
        id='treatment_year'
        )
    ], style={'display':'inline-block', 'width':'10%'}),

    #Right main
    html.Div(
        [
            #Graph container
            html.Div(
                dcc.Graph(
                    id='hn_sankey',
                    style={'height': '50vh'}
                    )
            ),

            #Slider container
            html.Div(
                dcc.Slider(
                    min=0,max=4,
                    step=1,
                    value=2,
                    id='sankey_slider',
                    tooltip={
                        "always_visible": True
                    }
                    )
            ),
            html.B(children='Condition', style={'textAlign':'left'}),
            dcc.Checklist(
            [{"label":"Select all conditions", "value":"All"}],
            value=[],
            id='all_or_none'
            ),
            dcc.Checklist(
            options,
            value=["Malignant neoplasm of nipple and areola of female breast"],
            inline=True,
            id='condition'
        )
        ], style={'display':'inline-block', 'width':'80%', 'height':'900px'}
    )
])

#controls
@callback(
    Output(component_id="condition", component_property="value"),
    Output(component_id="all_or_none", component_property="value"),
    Input(component_id="condition", component_property="value"),
    Input(component_id="all_or_none", component_property="value"),
    prevent_initial_call=True,
)
def select_all_none(conds_selected, all_selected):
    ctx=callback_context
    input_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if input_id=="condition":
        all_selected = ["All"] if set (conds_selected) == set(options) else []
    else:
        conds_selected = options if all_selected else []
    return conds_selected, all_selected

@callback(
    Output(component_id="first_treatment", component_property="value"),
    Output(component_id="all_drugs_or_none", component_property="value"),
    Input(component_id="first_treatment", component_property="value"),
    Input(component_id="all_drugs_or_none", component_property="value"),
    prevent_initial_call=True,
)
def select_all_drugs(drugs_selected, all_drugs_selected):
    ctx=callback_context
    input_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if input_id=="first_treatment":
        all_drugs_selected = ["Alldrugs"] if set (drugs_selected) == set(drugoptions) else []
    else:
        drugs_selected = drugoptions if all_drugs_selected else []
    return drugs_selected, all_drugs_selected

@callback(
    Output(component_id='hn_sankey', component_property='figure', allow_duplicate=True),
    Input(component_id='person_gender', component_property='value'),
    Input(component_id='age_at_treatment', component_property='value'),
    Input(component_id='treatment_year', component_property='value'),
    Input(component_id='first_treatment', component_property='value'),
    Input(component_id='sankey_slider', component_property='value'),
    Input(component_id='condition', component_property='value'),
    prevent_initial_call='initial_duplicate',
)
def update_graph(selected_genders, selected_ages, selected_years, selected_treatments, slider_value, selected_conditions):
    global small_nodup
    nodup = small_nodup.copy()
    nodup = nodup[nodup[['cond_0','cond_1','cond_2','cond_3',]].isin(selected_conditions).any(axis=1)]
    nodup = nodup[nodup['gender_concept_label'].isin(selected_genders)]
    nodup = nodup[nodup['age_at_treatment'] >= selected_ages[0]]
    nodup = nodup[nodup['age_at_treatment'] <= selected_ages[1]]
    nodup = nodup[nodup['drug_exposure_year'].isin(selected_years)]

    #reshape DF
    #pivot the DF from long to wide
    pivoted = nodup.pivot(index='person_id', columns='readministration', values='drug_concept_label').reset_index()
    # add the prefix 'drug' to every instance
    prefixed = pivoted.add_prefix('drug')
    #remove the word 'drug' from other variables
    df = prefixed.rename(columns={"drugperson_id": "person_id", "readministration":"index"})
    df.sort_values('drug0')
    #add a value of 1 to all data points for sums in the visualization
    df["count"] = 1

    #other filters
    column_names = list(df.columns.values)
    drug_num = column_names[1:slider_value+1] 
    dff = df[df['drug0'].isin(selected_treatments)]
    return genSankey(dff, cat_cols=drug_num, value_cols='count', title='Sankey Diagram')



if __name__ == '__main__':
    app.run(debug=True)

