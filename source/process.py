# -*- coding: utf-8 -*-
from datetime import datetime
import os
import sys
import pandas as pd
from common import get_graphql_data, write_text, write_ranking_repo, set_access_token
import inspect

set_access_token(sys.argv[1])

# languages = ['Python']  # For test
# languages_md = ['Python']  # For test
# table_of_contents = """
# * [Python](#python)"""  # For test

languages = ['LLM', 'ChatGPT', 'OpenAI', 'Deepseek', 'LLaMA', 'Chatbot', 'AI Agents', 'Claude', 'RAG', 'Mistral', 'Transformer', 'MoE', 'AGI', 'Generative AI', 'AI']
languages_md = ['LLM', 'ChatGPT','OpenAI', 'Deepseek', 'LLaMA', 'Chatbot', 'AI_Agents', 'Claude', 'RAG', 'Mistral', 'Transformer', 'MoE', 'AGI', 'Generative_AI', 'AI']
table_of_contents = """
 * [LLM](#LLM)
 * [ChatGPT](#ChatGPT) 
 * [OpenAI](#OpenAI)
 * [Deepseek](#Deepseek)
 * [LLaMA](#LLaMA)
 * [Chatbot](#Chatbot)
 * [AI Agents](#AI_Agents)
 * [Claude](#Claude)
 * [RAG](#RAG)
 * [Mistral](#Mistral)
 * [Transformer](#Transformer)
 * [MoE](#MoE)
 * [AGI](#AGI)
 * [Generative_AI](#Generative_AI)
 * [AI](#AI)
"""

class ProcessorGQL(object):
    """
    Github GraphQL API v4
    ref: https://docs.github.com/en/graphql
    use graphql to get data, limit 5000 points per hour
    check rate_limit with :
    curl -H "Authorization: bearer your-access-token" -X POST -d "{\"query\": \"{ rateLimit { limit cost remaining resetAt used }}\" }" https://api.github.com/graphql
    """

    def __init__(self):
        self.gql_format = """query{
    search(query: "%s", type: REPOSITORY, first:%d %s) {
      pageInfo { endCursor }
                edges {
                    node {
                        ...on Repository {
                            id
                            name
                            url
                            forkCount
                            stargazerCount
                            owner {
                                login
                            }
                            description
                            pushedAt
                            primaryLanguage {
                                name
                            }
                            openIssues: issues(states: OPEN) {
                                totalCount
                            }
                        }
                    }
                }
            }
        }
        """
        self.bulk_size = 50
        self.bulk_count = 2
        self.gql_stars_lang = self.gql_format % ("%s stars:>0 sort:stars", self.bulk_size, "%s")

        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url', 'username', 'issues',
                    'last_commit', 'description']

    @staticmethod
    def parse_gql_result(result):
        res = []
        for repo in result["data"]["search"]["edges"]:
            repo_data = repo['node']
            res.append({
                'name': repo_data['name'],
                'stargazers_count': repo_data['stargazerCount'],
                'forks_count': repo_data['forkCount'],
                'language': repo_data['primaryLanguage']['name'] if repo_data['primaryLanguage'] is not None else None,
                'html_url': repo_data['url'],
                'owner': {
                    'login': repo_data['owner']['login'],
                },
                'open_issues_count': repo_data['openIssues']['totalCount'],
                'pushed_at': repo_data['pushedAt'],
                'description': repo_data['description']
            })
        return res

    def get_repos(self, qql):
        cursor = ''
        repos = []
        for i in range(0, self.bulk_count):
            repos_gql = get_graphql_data(qql % cursor)
            cursor = ', after:"' + repos_gql["data"]["search"]["pageInfo"]["endCursor"] + '"'
            repos += self.parse_gql_result(repos_gql)
        return repos

    def get_all_repos(self):
        repos_languages = {}
        for lang in languages:
            print("Get most stars repos of {}...".format(lang))
            repos_languages[lang] = self.get_repos(self.gql_stars_lang % (lang, '%s'))
            print("Get most stars repos of {} success!".format(lang))
        return repos_languages


class WriteFile(object):
    def __init__(self, repos_languages):
        self.repos_languages = repos_languages
        self.col = ['rank', 'item', 'repo_name', 'stars', 'forks', 'language', 'repo_url', 'username', 'issues',
                    'last_commit', 'description']
        self.repo_list = []
        self.yesterday_ranks = self.load_yesterday_ranks()
        for i in range(len(languages)):
            lang = languages[i]
            lang_md = languages_md[i]
            self.repo_list.append({
                "desc": "Forks",
                "desc_md": "Forks",
                "title_readme": lang_md,
                "title_100": f"Top 100 Stars in {lang_md}",
                "file_100": f"{lang}.md",
                "data": repos_languages[lang],
                "item": lang,
            })

    def load_yesterday_ranks(self):
        from datetime import datetime, timedelta
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        csv_path = f'../Data/github-ranking-{yesterday}.csv'
        if not os.path.exists(csv_path):
            print(f"No yesterday data found: {csv_path}")
            return None
        df = pd.read_csv(csv_path)
        ranks = {}
        for _, row in df.iterrows():
            repo_url = row['repo_url']
            item = row['item']
            rank_val = row['rank']
            if isinstance(rank_val, str):
                import re
                match = re.match(r'^(\d+)', rank_val)
                if match:
                    rank_val = int(match.group(1))
            ranks[(repo_url, item)] = rank_val
        print(f"Loaded yesterday ranks from {csv_path}")
        return ranks

    def get_rank_changes(self, repos, item):
        if self.yesterday_ranks is None:
            return None
        rank_changes = {}
        for idx, repo in enumerate(repos):
            repo_url = repo['html_url']
            key = (repo_url, item)
            if key in self.yesterday_ranks:
                old_rank = self.yesterday_ranks[key]
                new_rank = idx + 1
                change = old_rank - new_rank
                rank_changes[repo_url] = change
        return rank_changes

    @staticmethod
    def write_head_contents():
        # write the head and contents of README.md
        write_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        head_contents = inspect.cleandoc("""[Github Ranking AI](./README.md)
            ==========

            **A list of the most github stars and forks repositories.**

            *Last Automatic Update Time: {write_time}*

            ## Table of Contents

            """.format(write_time=write_time)) + table_of_contents
        write_text("../README.md", 'w', head_contents)

    def write_readme_lang_md(self):
        os.makedirs('../Top100', exist_ok=True)
        for repo in self.repo_list:
            title_readme, title_100, file_100, data, item = repo["title_readme"], repo["title_100"], repo["file_100"], repo["data"], repo["item"]
            rank_changes = self.get_rank_changes(data, item)
            write_text('../README.md', 'a',
                       f"\n## {title_readme}\n\nThis is top 10, for more click **[{title_100}](Top100/{file_100})**\n\n")
            write_ranking_repo('../README.md', 'a', data[:10], rank_changes)
            print(f"Save {title_readme} in README.md!")

            write_text(f"../Top100/{file_100}", "w",
                       f"[Github Ranking](../README.md)\n==========\n\n## {title_100}\n\n")
            write_ranking_repo(f"../Top100/{file_100}", 'a', data, rank_changes)
            print(f"Save {title_100} in Top100/{file_100}!\n")

    def repo_to_df(self, repos, item):
        # prepare for saving data to csv file
        repos_list = []
        for idx, repo in enumerate(repos):
            repo_info = [idx + 1, item, repo['name'], repo['stargazers_count'], repo['forks_count'], repo['language'],
                         repo['html_url'], repo['owner']['login'], repo['open_issues_count'], repo['pushed_at'],
                         repo['description']]
            repos_list.append(repo_info)
        return pd.DataFrame(repos_list, columns=self.col)

    def save_to_csv(self):
        # save top100 repos info to csv file in Data/github-ranking-year-month-day.md
        df_all = pd.DataFrame(columns=self.col)
        for repo in self.repo_list:
            df_repos = self.repo_to_df(repos=repo["data"], item=repo["item"])
            df_all = df_all._append(df_repos, ignore_index=True)

        save_date = datetime.utcnow().strftime("%Y-%m-%d")
        os.makedirs('../Data', exist_ok=True)
        df_all.to_csv('../Data/github-ranking-' + save_date + '.csv', index=False, encoding='utf-8')
        print('Save data to Data/github-ranking-' + save_date + '.csv')


def run_by_gql():
    ROOT_PATH = os.path.abspath(os.path.join(__file__, "../../"))
    os.chdir(os.path.join(ROOT_PATH, 'source'))

    processor = ProcessorGQL()  # use Github GraphQL API v4
    repos_languages = processor.get_all_repos()
    wt_obj = WriteFile(repos_languages)
    wt_obj.write_head_contents()
    wt_obj.write_readme_lang_md()
    wt_obj.save_to_csv()


if __name__ == "__main__":
    t1 = datetime.now()
    run_by_gql()
    print("Total time: {}s".format((datetime.now() - t1).total_seconds()))